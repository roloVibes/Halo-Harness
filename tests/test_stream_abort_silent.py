"""tests.test_stream_abort_silent -- an abort while the upstream call is still
SILENT (no status line yet: the provider is thinking, or a sub-agent's call
waits behind a steer) ends `stream_completion` cleanly, on this platform
(Halo 3.1.7.0: the Session steer test found that a steer typed while a
sub-agent's call was silent killed the sub-agent on Linux -- the force-shut
socket raised `RemoteDisconnected` out of getresponse(), which nothing
mapped to the abort -- and waited for the provider's first byte on Windows,
where SHUT_RDWR never wakes a pending recv). Pinned:

1. the phase-1 abort watcher wakes the blocked read within a second and the
   generator ends with no event and no exception, on the plain call path
   (`HALO_GOVERNOR=0`: every host the Governor does not know);
2. the same through the governed path; the mock saw exactly one request
   each time (nothing was retried as a failure).
Run: python -m tests.test_stream_abort_silent
"""
from __future__ import annotations

import os
import sys
import threading
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402
from tests.helpers.mock_openai import SCENARIOS, MockUpstream, _finish  # noqa: E402
from tests.test_stream import _req  # noqa: E402

from halo_harness.providers.stream import stream_completion  # noqa: E402

test, TESTS = new_registry()
NAME = "held-silent-abort"


def _held_scenario(gate: threading.Event, seen: list):
    """The upstream takes the request and says nothing until `gate` is set (a 600 s hold at most)."""
    def step(handler, body):
        seen.append(body)
        gate.wait(600)
        try:
            _finish(handler, [{"choices": [{"index": 0, "delta": {"role": "assistant"}}]},
                              {"choices": [{"index": 0, "delta": {"content": "late"}}]},
                              {"choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}]}])
        except OSError:
            pass  # the client is gone: the aborted request's socket is closed
    return step


def _abort_while_silent(ctx: Ctx, governor: str) -> None:
    """`HALO_GOVERNOR` picks the path: "0" is the plain `do_call()` (the test suite's default, and every
    host the Governor does not know), "1" the governed one that wraps a post-connect failure itself."""
    gate, seen, got = threading.Event(), [], {}
    SCENARIOS[NAME] = _held_scenario(gate, seen)
    mock = MockUpstream().start()
    saved = os.environ.get("HALO_GOVERNOR")
    os.environ["HALO_GOVERNOR"] = governor
    try:
        abort = threading.Event()

        def consume():
            t0 = time.monotonic()
            try:
                got["events"] = list(stream_completion(_req(mock, NAME), abort=abort))
            except BaseException as e:  # noqa: BLE001 -- the check names it
                got["error"] = f"{type(e).__name__}: {e}"
            got["took"] = time.monotonic() - t0

        th = threading.Thread(target=consume, daemon=True)
        th.start()
        deadline = time.monotonic() + 10
        while not seen and time.monotonic() < deadline:
            time.sleep(0.02)
        ctx.check(f"the upstream got the request and holds it, seen {len(seen)}", len(seen) == 1)
        t_abort = time.monotonic()
        abort.set()
        th.join(5.0)
        dt = time.monotonic() - t_abort
        ctx.check(f"the blocked read woke within 1.5 s of the abort on {sys.platform}, took {dt:.2f} s (alive={th.is_alive()})",
                  not th.is_alive() and dt < 1.5)
        ctx.check(f"no error reached the caller, got {got.get('error')!r}", "error" not in got)
        ctx.check(f"no event came out of the aborted call, got {len(got.get('events') or [])}", got.get("events") == [])
        time.sleep(0.3)
        ctx.check(f"the mock saw one request, never a retry, got {len(seen)}", len(seen) == 1)
    finally:
        if saved is None:
            os.environ.pop("HALO_GOVERNOR", None)
        else:
            os.environ["HALO_GOVERNOR"] = saved
        gate.set()
        time.sleep(0.1)
        mock.stop()
        SCENARIOS.pop(NAME, None)


@test
def test_an_abort_during_the_silent_phase_ends_the_plain_call_cleanly_and_quickly(ctx: Ctx):
    _abort_while_silent(ctx, "0")


@test
def test_the_same_through_the_governed_path(ctx: Ctx):
    _abort_while_silent(ctx, "1")


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
