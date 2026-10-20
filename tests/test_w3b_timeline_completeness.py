"""tests.test_w3b_timeline_completeness -- W3b item 11: the per-turn
timeline (halo_harness/debug_timeline.py) records hooks (event name +
duration), permission waits (start, end, decision) and compactions, and
each `Session` keeps its OWN `TurnTimeline` instance (never the module's
shared default) so parallel sub-agent turns can't interleave into one
record. 3.1.5.0 R1: runs on the mock OpenAI-chat route (the same
`MockUpstream` + scenario shape tests/test_loop_retries.py uses): the model
asks for one Read, the next request answers "done".
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
import threading
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.fake_home import build_fake_home
from tests.helpers.mock_openai import SCENARIOS, MockUpstream, _finish
from tests.helpers.provider_env_defaults import ensure_default_provider_credentials
from tests.helpers.runner import Ctx, new_registry, print_results, run_all

os.environ["BRIDGE_TEST_HOME"] = tempfile.mkdtemp(prefix="w3b-timeline-scratchhome-")
ensure_default_provider_credentials()

test, TESTS = new_registry()

REPO_DIR = Path(__file__).resolve().parent.parent
_HOOK_SCRIPT_ARGV = [sys.executable, "-m", "tests.helpers.hook_scripts"]


def _read_then_done(target: Path):
    def _scn(h, body):
        messages = (body or {}).get("messages") or []
        if any(m.get("role") == "tool" for m in messages):
            _finish(h, [
                {"choices": [{"index": 0, "delta": {"role": "assistant"}}]},
                {"choices": [{"index": 0, "delta": {"content": "done"}}]},
                {"choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}]},
            ])
        else:
            _finish(h, [
                {"choices": [{"index": 0, "delta": {"role": "assistant"}}]},
                {"choices": [{"index": 0, "delta": {"tool_calls": [
                    {"index": 0, "id": "call_read", "type": "function",
                     "function": {"name": "Read", "arguments": json.dumps({"file_path": str(target)})}},
                ]}}]},
                {"choices": [{"index": 0, "delta": {}, "finish_reason": "tool_calls"}]},
            ])
    return _scn


def _new_session(fh, mock, scenario: str, *, permission_engine=None, hook_runner=None):
    from halo_harness.agent.assemble import SessionContext
    from halo_harness.agent.loop import Session
    from halo_harness.model import ModelProfile, parse_model_ref
    from halo_harness.permissions import PermissionEngine
    from halo_harness.providers.stream import ProviderCreds
    os.environ["BRIDGE_OPENROUTER_BASE_URL"] = mock.base_url
    model = f"or:mock/{scenario}"
    return Session(
        cwd=fh["proj"], model_ref=parse_model_ref(model), model_profile=ModelProfile(),
        creds=ProviderCreds(base_url=mock.base_url, api_key="k"),
        state_dir=Path(tempfile.mkdtemp(prefix="w3b-timeline-sdir-")), model_label=model,
        session_context=SessionContext(cwd=fh["proj"], model_label=model), openrouter_base_url=mock.base_url,
        max_turns=6, permission_engine=permission_engine or PermissionEngine(mode="auto", cwd=fh["proj"]),
        hook_runner=hook_runner,
    )


def _wait_for_event_kind(collected, kind, timeout=10.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        for e in list(collected):
            if e.kind == kind:
                return e
        time.sleep(0.02)
    return None


def _target(fh, name: str) -> Path:
    target = fh["proj"] / name
    target.write_text("hi\n", encoding="utf-8")
    return target


@test
def test_hook_duration_recorded_in_the_turns_timeline(ctx: Ctx):
    """A real PreToolUse hook (json_allow -- exit 0, no rewrite) fires
    during a real turn -- the timeline's own `hooks` list gets one entry
    naming the event and a real (>=0) duration, via `Session._run_hook`."""
    from halo_harness.hooks import HookDef, HookRunner
    fh = build_fake_home()
    SCENARIOS["w3b-hook"] = _read_then_done(_target(fh, "f.txt"))
    mock = MockUpstream().start()
    try:
        env = dict(os.environ, PYTHONPATH=str(REPO_DIR))
        runner = HookRunner(
            {"PreToolUse": [HookDef(type="command", matcher="Read", args=_HOOK_SCRIPT_ARGV + ["json_allow"])]},
            cwd=fh["proj"], session_id="w3b-hook-timeline", transcript_path=str(fh["proj"] / "t.jsonl"),
            effective_env=env,
        )
        session = _new_session(fh, mock, "w3b-hook", hook_runner=runner)
        list(session.turn("read f.txt"))
        record = session._timeline.last_turn()
        ctx.check(f"a timeline record was captured, got {record}", record is not None)
        pre_hooks = [h for h in ((record or {}).get("hooks") or []) if h.get("event") == "PreToolUse"]
        ctx.check(f"PreToolUse recorded in the timeline's own hooks list, got {pre_hooks}", len(pre_hooks) == 1)
        ctx.check(f"a real non-negative duration was recorded, got {pre_hooks!r}",
                  bool(pre_hooks) and isinstance(pre_hooks[0].get("duration_ms"), (int, float))
                  and pre_hooks[0]["duration_ms"] >= 0)
        session.close_runtimes()
    finally:
        mock.stop()
        os.environ.pop("BRIDGE_OPENROUTER_BASE_URL", None)


def _ask_session(fh, mock, scenario: str):
    from halo_harness.permissions import PermissionEngine
    engine = PermissionEngine(mode="default", cwd=Path(tempfile.mkdtemp(prefix="w3b-permwait-")))
    session = _new_session(fh, mock, scenario, permission_engine=engine)
    session.interactive = True
    return session


@test
def test_permission_wait_recorded_with_its_decision_in_the_turns_timeline(ctx: Ctx):
    """A real interactive permission ask (a Read outside the engine's own
    cwd), answered 'allow' from another thread -- the timeline's own
    `permission_waits` gets one entry with that decision and a real
    start/end pair."""
    from halo_harness.permissions import Decision
    fh = build_fake_home()
    SCENARIOS["w3b-allow"] = _read_then_done(_target(fh, "f.txt"))
    mock = MockUpstream().start()
    try:
        session = _ask_session(fh, mock, "w3b-allow")
        collected: list = []
        t = threading.Thread(target=lambda: collected.extend(session.turn("read f.txt")))
        t.start()
        req = _wait_for_event_kind(collected, "permission_request")
        ctx.check("permission_request shown", req is not None)
        ok = session.resolve_permission(req.data["id"], Decision("allow", "test allow")) if req else False
        ctx.check("resolve_permission accepted", ok)
        t.join(timeout=15)
        waits = ((session._timeline.last_turn() or {}).get("permission_waits")) or []
        ctx.check(f"exactly one permission wait recorded, got {waits}", len(waits) == 1)
        ctx.check(f"resolved decision is 'allow', got {waits!r}", bool(waits) and waits[0].get("decision") == "allow")
        ctx.check(f"end_ms is at or after start_ms, got {waits!r}",
                  bool(waits) and waits[0]["end_ms"] >= waits[0]["start_ms"])
        session.close_runtimes()
    finally:
        mock.stop()
        os.environ.pop("BRIDGE_OPENROUTER_BASE_URL", None)


@test
def test_dismissed_permission_wait_records_a_decision_of_dismissed(ctx: Ctx):
    """Esc/abort mid-ask (`_apply_permission_decision`'s own `decision is
    None` branch) must still leave a recognizable entry -- "dismissed",
    never a crash or a silently-missing wait."""
    fh = build_fake_home()
    SCENARIOS["w3b-dismiss"] = _read_then_done(_target(fh, "f.txt"))
    mock = MockUpstream().start()
    try:
        session = _ask_session(fh, mock, "w3b-dismiss")
        collected: list = []
        t = threading.Thread(target=lambda: collected.extend(session.turn("read f.txt")))
        t.start()
        req = _wait_for_event_kind(collected, "permission_request")
        ctx.check("permission_request shown", req is not None)
        session.abort.set()
        t.join(timeout=15)
        waits = ((session._timeline.last_turn() or {}).get("permission_waits")) or []
        ctx.check(f"exactly one permission wait recorded, got {waits}", len(waits) == 1)
        ctx.check(f"an aborted/dismissed ask records 'dismissed', got {waits!r}",
                  bool(waits) and waits[0].get("decision") == "dismissed")
        session.close_runtimes()
    finally:
        mock.stop()
        os.environ.pop("BRIDGE_OPENROUTER_BASE_URL", None)


@test
def test_each_session_keeps_its_own_timeline_instance_never_the_shared_default(ctx: Ctx):
    """W3b item 11's own core architectural fix: two Sessions (standing in
    for a parent and a parallel sub-agent -- agent/subagent.py's own child
    Session is built exactly the same way) must never share one
    `TurnTimeline`, nor the `debug_timeline` module's own shared default."""
    from halo_harness import debug_timeline
    fh = build_fake_home()
    mock = MockUpstream().start()
    try:
        session_a = _new_session(fh, mock, "model")
        session_b = _new_session(fh, mock, "model")
        ctx.check("two independent TurnTimeline instances", session_a._timeline is not session_b._timeline)
        ctx.check("neither is the debug_timeline module's own shared default",
                  session_a._timeline is not debug_timeline._default_timeline
                  and session_b._timeline is not debug_timeline._default_timeline)
        session_a.close_runtimes()
        session_b.close_runtimes()
    finally:
        mock.stop()
        os.environ.pop("BRIDGE_OPENROUTER_BASE_URL", None)


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
