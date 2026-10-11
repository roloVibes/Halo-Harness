"""tests.test_review2_round9 -- pins for the vibes/review.md fix pass, round 9
(TUI + CLI/doctor), the plain (no Textual) half:

  * f67  an xclip-style tool that daemonizes keeps its stdout open, so a
        captured stdout pipe never closed and a successful copy was reported
        as failed after the timeout; stderr now lands in a file
  * f69  shadow snapshots ran git on the UI thread and raced the Bash
        snapshot worker; they go through one FIFO worker under a lock
  * f75  stream-json: background notices repeated in every later result;
        a budget stop dropped the final assistant line

Round 9b holds the TUI pilots (68, 70-74, the 75 auto-title counter) and
round 9c the CLI and doctor pins (76-78, 80, 82, 83).
"""
from __future__ import annotations

import io
import json
import os
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.runner import Ctx, new_registry, print_results, run_all

REPO_DIR = Path(__file__).resolve().parent.parent
test, TESTS = new_registry()

if "BRIDGE_TEST_HOME" not in os.environ:
    os.environ["BRIDGE_TEST_HOME"] = tempfile.mkdtemp(prefix="r9-home-")


# ---- f67: the external clipboard tool ----------------------------------------

@test
def test_f67_copy_argv_sends_stdout_to_devnull_and_stderr_to_a_file(ctx: Ctx):
    import halo_harness.tui.clipboard as clip
    seen: dict = {}

    def _fake_run(argv, **kwargs):
        seen.update(kwargs)
        return SimpleNamespace(returncode=0)

    real = clip.subprocess.run
    clip.subprocess.run = _fake_run
    try:
        ok = clip._copy_argv(["xclip"], "hello", timeout_s=3.0)
    finally:
        clip.subprocess.run = real
    ctx.check("reports success", ok is True)
    ctx.check(f"stdout is DEVNULL, got {seen.get('stdout')!r}", seen.get("stdout") == subprocess.DEVNULL)
    ctx.check("no captured stdout pipe", not seen.get("capture_output"))
    ctx.check(f"stderr is a file object, not a pipe, got {seen.get('stderr')!r}",
              hasattr(seen.get("stderr"), "fileno") and seen.get("stderr") not in (subprocess.PIPE, subprocess.DEVNULL))


@test
def test_f67_a_daemon_holding_stdout_does_not_stall_a_successful_copy(ctx: Ctx):
    import halo_harness.tui.clipboard as clip
    code = ("import subprocess, sys; "
            "subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(4)']); sys.stdin.read()")
    started = time.monotonic()
    ok = clip._copy_argv([sys.executable, "-c", code], "hello", timeout_s=3.0)
    elapsed = time.monotonic() - started
    ctx.check("the copy is reported as a success", ok is True)
    ctx.check(f"it returned without waiting out the timeout, took {elapsed:.2f}s", elapsed < 2.0)


@test
def test_f67_a_failing_tool_keeps_its_error_text(ctx: Ctx):
    import halo_harness.tui.clipboard as clip
    code = "import sys; sys.stderr.write('no display available'); sys.exit(3)"
    ok = clip._copy_argv([sys.executable, "-c", code], "x", timeout_s=5.0)
    ctx.check("a non-zero exit is a failure", ok is False)
    ctx.check(f"stderr is kept, got {clip.last_copy_error()!r}", "no display available" in clip.last_copy_error())
    clip._copy_argv([sys.executable, "-c", "pass"], "x", timeout_s=5.0)
    ctx.check("a clean run clears it", clip.last_copy_error() == "")


# ---- f69: shadow snapshots off the UI thread, serialized -----------------------

def _shadow_app(shadow_dir: Path):
    controller = SimpleNamespace(shadow_dir=shadow_dir)
    return SimpleNamespace(controller=controller, cwd=shadow_dir, _pending_tool_inputs={})


@test
def test_f69_a_write_snapshot_runs_on_the_shadow_worker_not_the_caller(ctx: Ctx):
    from halo_harness import shadow
    from halo_harness.tui.dispatch import _maybe_record_shadow_step
    work = Path(tempfile.mkdtemp(prefix="r9-shadow-"))
    target = work / "doc.txt"
    target.write_text("v1", encoding="utf-8")
    app = _shadow_app(work / "store")
    app._pending_tool_inputs["t1"] = ("Write", {"file_path": str(target)}, True)
    threads: list = []
    real = shadow.ShadowStore.record_step

    def _slow(self, files, **kw):
        threads.append(threading.current_thread())
        time.sleep(0.4)
        return real.__wrapped__(self, files, **kw)

    shadow.ShadowStore.record_step = shadow._locked(_slow)
    try:
        started = time.monotonic()
        _maybe_record_shadow_step(app, "t1", True, None, turn=1)
        returned_in = time.monotonic() - started
        ctx.check(f"the hook returned before the slow snapshot finished ({returned_in:.2f}s)", returned_in < 0.3)
        ctx.check("the snapshot finishes on the worker", shadow.drain_jobs(10.0))
    finally:
        shadow.ShadowStore.record_step = real
    ctx.check("it ran on a thread other than the caller's",
              threads and threads[0] is not threading.current_thread())
    ctx.check("the step was recorded", len(shadow.ShadowStore(work / "store").steps) == 1)


@test
def test_f69_jobs_run_in_submission_order(ctx: Ctx):
    from halo_harness import shadow
    order: list = []
    for i in range(25):
        shadow.enqueue_job(lambda i=i: order.append(i))
    shadow.drain_jobs(10.0)
    ctx.check(f"FIFO order, got {order}", order == list(range(25)))


@test
def test_f69_concurrent_recording_on_one_store_directory_loses_no_step(ctx: Ctx):
    from halo_harness.shadow import ShadowStore
    work = Path(tempfile.mkdtemp(prefix="r9-shadow-lock-"))
    store_dir = work / "store"
    ShadowStore(store_dir)

    def _record(tag: str) -> None:
        for n in range(4):
            f = work / f"{tag}{n}.txt"
            f.write_text(f"{tag}{n}", encoding="utf-8")
            ShadowStore(store_dir).record_step({str(f): f"{tag}{n}"}, label=f"{tag}{n}")

    threads = [threading.Thread(target=_record, args=(t,)) for t in ("a", "b")]
    for t in threads:
        t.start()
    for t in threads:
        t.join(60)
    steps = ShadowStore(store_dir).steps
    ctx.check(f"all 8 steps are in the index, got {len(steps)}", len(steps) == 8)
    log = subprocess.run(["git", "-C", str(store_dir / "shadow"), "rev-list", "--count", "HEAD"],
                         capture_output=True, text=True).stdout.strip()
    ctx.check(f"and 8 commits, got {log!r}", log == "8")


@test
def test_f69_the_rewind_workers_drain_queued_snapshots_first(ctx: Ctx):
    import halo_harness.tui.slash as slash
    from halo_harness import shadow
    done: list = []
    shadow.enqueue_job(lambda: (time.sleep(0.3), done.append("snap")))
    seen: list = []
    controller = SimpleNamespace(rewind_apply=lambda sid, verb="": seen.append(list(done)) or {"files": []})
    app = SimpleNamespace(controller=controller,
                          call_from_thread=lambda *a, **k: None, transcript=SimpleNamespace(add_note=None), notify=None)
    slash._apply_rewind_worker(app, "abc", "undo")
    ctx.check(f"the queued snapshot had landed before the restore, saw {seen}", seen == [["snap"]])


# ---- f75: stream-json state per result ---------------------------------------------

def _sink(**kw):
    from halo_harness.output import StreamJsonSink
    buf = io.StringIO()
    sink = StreamJsonSink(session_id="s", cwd="/tmp/x", model="m", permission_mode="auto", stream=buf, **kw)
    return sink, buf


def _lines(buf) -> list:
    return [json.loads(x) for x in buf.getvalue().splitlines() if x.strip()]


@test
def test_f75_background_notices_are_not_repeated_in_a_later_result(ctx: Ctx):
    from halo_harness import events as ev
    sink, buf = _sink()
    sink.add_background_notice("job 1 finished")
    def turn(n):
        yield ev.message_start(turn=n)
        yield ev.text_delta("ok", turn=n)
        yield ev.message_end(turn=n, stop_reason="end_turn")
        yield ev.turn_done(turn=n)

    sink.consume(turn(1))
    sink.consume(turn(2))
    results = [l for l in _lines(buf) if l["type"] == "result"]
    ctx.check(f"first result carries the notice, got {results[0].get('background_notices')}",
              results[0].get("background_notices") == ["job 1 finished"])
    ctx.check(f"second result does not, got {results[1].get('background_notices')}",
              not results[1].get("background_notices"))


@test
def test_f75_budget_stop_still_writes_the_final_assistant_line(ctx: Ctx):
    from halo_harness import events as ev
    sink, buf = _sink(max_budget_usd=0.01)
    def _stream():
        yield ev.message_start(turn=1)
        yield ev.text_delta("the last words", turn=1)
        yield ev.message_end(turn=1, stop_reason="end_turn", cost_usd=0.5)
        yield ev.turn_done(turn=1)

    sink.consume(_stream())
    lines = _lines(buf)
    types = [l["type"] for l in lines]
    assistant = [l for l in lines if l["type"] == "assistant"]
    ctx.check(f"an assistant line precedes the result, got {types}", assistant and types[-1] == "result")
    ctx.check("it carries the text", "the last words" in json.dumps(assistant[-1]))
    ctx.check("the result is the budget error", lines[-1]["subtype"] == "error_max_budget_usd")


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
