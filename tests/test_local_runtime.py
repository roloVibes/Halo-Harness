"""tests.test_local_runtime -- Halo 2.0.3 round 5c: the managed llama-
server/mlx_lm child-process registry (start, record, stop by name, stop-
all-except-kept) against a FAKE runtime binary -- a tiny Python stub THIS
TEST writes to a scratch file and runs as a real subprocess (never a real
llama-server/mlx_lm), serving the same `/v1/models` shape mock_openai.py's
servers answer. Never touches the real ~/.halo (state_dir is always an
explicit fresh tempdir).
"""
from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.runner import Ctx, new_registry, print_results, run_all

test, TESTS = new_registry()

_STUB_LISTENS = '''
import json, sys
from http.server import BaseHTTPRequestHandler, HTTPServer

port = int(sys.argv[sys.argv.index("--port") + 1])


class H(BaseHTTPRequestHandler):
    def log_message(self, *a): pass

    def do_GET(self):
        if self.path.rstrip("/").endswith("/models"):
            body = json.dumps({"object": "list", "data": [{"id": "stub-model"}]}).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        else:
            self.send_response(404)
            self.end_headers()


HTTPServer(("127.0.0.1", port), H).serve_forever()
'''

_STUB_NEVER_LISTENS = "import time\ntime.sleep(60)\n"

_STUB_LISTENS_AFTER_DELAY = '''
import json, sys, time
from http.server import BaseHTTPRequestHandler, HTTPServer

port = int(sys.argv[sys.argv.index("--port") + 1])
time.sleep(1.5)


class H(BaseHTTPRequestHandler):
    def log_message(self, *a): pass

    def do_GET(self):
        if self.path.rstrip("/").endswith("/models"):
            body = json.dumps({"object": "list", "data": [{"id": "stub-model"}]}).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        else:
            self.send_response(404)
            self.end_headers()


HTTPServer(("127.0.0.1", port), H).serve_forever()
'''

_STUB_EXITS_WITH_STDERR = (
    'import sys\n'
    'sys.stderr.write("boom: pretend model file could not be loaded\\n")\n'
    'sys.stderr.flush()\n'
    'sys.exit(1)\n'
)


def _write_stub(code: str) -> Path:
    d = Path(tempfile.mkdtemp(prefix="local-runtime-stub-"))
    p = d / "stub_runtime.py"
    p.write_text(code, encoding="utf-8")
    return p


def _posix_proc_state(pid):
    try:
        with open(f"/proc/{pid}/stat", "r") as f:
            content = f.read()
    except OSError:
        return None
    idx = content.rfind(")")
    if idx == -1:
        return None
    fields = content[idx + 1:].split()
    return fields[0] if fields else None


def _is_alive(pid) -> bool:
    """Cross-platform liveness check for a PID this test does not hold a
    `Popen` handle for (`start_managed_server` returns only the bare pid).
    `os.kill(pid, 0)`'s POSIX "signal 0" trick is not supported by
    Windows' own `os.kill` (CPython only maps SIGTERM/CTRL_* there), so
    Windows shells out to `tasklist` instead.

    FIX PASS (live run on Kali/WSL): a bare `os.kill(pid, 0)` on POSIX
    reports a ZOMBIE (already exited, not yet reaped by its parent) as
    "alive" -- the exact false positive that made `test_start_stop_
    managed_server_round_trip`/`test_stop_all_except_kept` look like
    they'd failed to stop anything when they actually had. This test IS
    the parent of the stub process (`start_managed_server` ran in THIS
    process), so it tries to reap it itself first (`os.waitpid(pid,
    os.WNOHANG)`, guarded for `ChildProcessError`), then falls back to
    reading `/proc/<pid>/stat`'s own state field -- `"Z"` reads as dead."""
    if not isinstance(pid, int):
        return False
    if sys.platform == "win32":
        out = subprocess.run(["tasklist", "/FI", f"PID eq {pid}", "/NH"], capture_output=True, text=True).stdout
        return str(pid) in out
    try:
        reaped, _status = os.waitpid(pid, os.WNOHANG)
        if reaped == pid:
            return False
    except ChildProcessError:
        pass
    except OSError:
        return False
    if _posix_proc_state(pid) == "Z":
        return False
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except OSError:
        return True


def _wait_until(predicate, *, timeout: float = 5.0) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(0.1)
    return predicate()


@test
def test_llama_server_argv_matches_the_brief_exactly(ctx: Ctx):
    from halo_harness.providers.local_runtime import llama_server_argv
    argv = llama_server_argv(["llama-server"], model_path="/models/x.gguf", port=1234, context_length=16384,
                              model="my-model")
    ctx.check(f"exact flag order, got {argv}",
              argv == ["llama-server", "-m", "/models/x.gguf", "--alias", "my-model", "-c", "16384", "-ngl", "99",
                       "-fa", "on", "--port", "1234", "--host", "127.0.0.1"])


@test
def test_llama_server_argv_omits_c_when_context_unknown(ctx: Ctx):
    from halo_harness.providers.local_runtime import llama_server_argv
    argv = llama_server_argv(["llama-server"], model_path="/models/x.gguf", port=1234)
    ctx.check(f"no -c flag, got {argv}", "-c" not in argv)


@test
def test_llama_server_argv_alias_present_only_when_model_given(ctx: Ctx):
    """Review fix pass (finding 12): `--alias <model id>` is what makes
    the served `/v1/models` id equal the Halo-side name llama-server was
    started under -- without it, llama-server reports the `-m` PATH as
    its own id (the llama.cpp server README's own example), which never
    matches the stem/registry key Halo looks context back up by."""
    from halo_harness.providers.local_runtime import llama_server_argv
    with_alias = llama_server_argv(["llama-server"], model_path="/models/x.gguf", port=1234, model="tiny-test-model")
    ctx.check(f"--alias present right after -m, got {with_alias}",
              with_alias[with_alias.index("-m") + 2:with_alias.index("-m") + 4] == ["--alias", "tiny-test-model"])
    without_alias = llama_server_argv(["llama-server"], model_path="/models/x.gguf", port=1234)
    ctx.check(f"no --alias when model is omitted, got {without_alias}", "--alias" not in without_alias)


@test
def test_mlx_lm_server_argv_matches_the_brief_exactly(ctx: Ctx):
    from halo_harness.providers.local_runtime import mlx_lm_server_argv
    argv = mlx_lm_server_argv([sys.executable, "-m", "mlx_lm.server"], model_path="/models/dir", port=4321)
    ctx.check(f"exact flags, got {argv}",
              argv == [sys.executable, "-m", "mlx_lm.server", "--model", "/models/dir", "--port", "4321"])


@test
def test_start_stop_managed_server_round_trip(ctx: Ctx):
    from halo_harness.providers.local_runtime import (load_registry, start_managed_server, stop_managed_server)
    state_dir = Path(tempfile.mkdtemp(prefix="local-runtime-state-"))
    stub = _write_stub(_STUB_LISTENS)
    entry, reason = start_managed_server(model="/models/qwen3.gguf", runtime="llama-server",
                                          binary_argv=[sys.executable, str(stub)], model_path="/models/qwen3.gguf",
                                          context_length=8192, state_dir=state_dir, startup_timeout=10.0)
    try:
        ctx.check(f"start succeeded, got reason={reason!r}", entry is not None)
        ctx.check(f"base_url uses the chosen port, got {entry.base_url}", entry.base_url.endswith(f":{entry.port}/v1"))
        recorded = load_registry(state_dir)
        ctx.check(f"registry has exactly one entry, got {recorded}", len(recorded) == 1)
        ctx.check(f"registry entry's model matches, got {recorded[0]}", recorded[0]["model"] == "/models/qwen3.gguf")
        ok, msg = stop_managed_server("/models/qwen3.gguf", state_dir=state_dir)
        ctx.check(f"stop succeeded, got {msg!r}", ok)
        ctx.check("registry is empty after stop", load_registry(state_dir) == [])
        ctx.check("process is no longer alive after stop", _wait_until(lambda: not _is_alive(entry.pid)))
    finally:
        if entry is not None:
            from halo_harness.providers.local_runtime import _terminate_pid
            _terminate_pid(entry.pid)


@test
def test_stop_from_a_fresh_process_perspective_reaps_without_a_popen_handle(ctx: Ctx):
    """FIX PASS: `halo local stop` normally runs in a FRESH process with
    no `Popen` handle at all for the pid it's stopping -- simulated here
    by forgetting this test's own handle (`_forget_popen`) before
    calling stop, forcing `_terminate_pid` down its SIGTERM+`waitpid`
    fallback path instead of the handle-based `terminate()+wait()` one.
    Pins that the fallback still actually reaps/kills the process (never
    leaves a zombie `_is_alive` would misreport as running)."""
    from halo_harness.providers.local_runtime import (_forget_popen, load_registry, start_managed_server,
                                                        stop_managed_server)
    state_dir = Path(tempfile.mkdtemp(prefix="local-runtime-state-"))
    stub = _write_stub(_STUB_LISTENS)
    entry, reason = start_managed_server(model="/models/fresh-proc.gguf", runtime="llama-server",
                                          binary_argv=[sys.executable, str(stub)], model_path="/models/fresh-proc.gguf",
                                          state_dir=state_dir, startup_timeout=10.0)
    try:
        ctx.check(f"start succeeded, got reason={reason!r}", entry is not None)
        ctx.check("forgetting the handle leaves no trace of it", _forget_popen(entry.pid) is not None)
        ok, msg = stop_managed_server("/models/fresh-proc.gguf", state_dir=state_dir)
        ctx.check(f"stop still succeeds with no handle, got {msg!r}", ok)
        ctx.check("registry is empty after stop", load_registry(state_dir) == [])
        ctx.check("process is no longer alive after the no-handle stop path",
                  _wait_until(lambda: not _is_alive(entry.pid)))
    finally:
        if entry is not None:
            from halo_harness.providers.local_runtime import _terminate_pid
            _terminate_pid(entry.pid)


@test
def test_stop_unknown_model_fails_plainly(ctx: Ctx):
    from halo_harness.providers.local_runtime import stop_managed_server
    state_dir = Path(tempfile.mkdtemp(prefix="local-runtime-state-"))
    ok, msg = stop_managed_server("no-such-model", state_dir=state_dir)
    ctx.check(f"unknown model -> (False, ...), got ({ok}, {msg!r})", ok is False and "no-such-model" in msg)


@test
def test_start_times_out_and_terminates_the_half_started_process(ctx: Ctx):
    from halo_harness.providers.local_runtime import start_managed_server
    state_dir = Path(tempfile.mkdtemp(prefix="local-runtime-state-"))
    stub = _write_stub(_STUB_NEVER_LISTENS)
    entry, reason = start_managed_server(model="never-ready", runtime="llama-server",
                                          binary_argv=[sys.executable, str(stub)], model_path="x.gguf",
                                          state_dir=state_dir, startup_timeout=1.5)
    ctx.check(f"start reports failure, got entry={entry!r}", entry is None)
    ctx.check(f"reason mentions the timeout, got {reason!r}", reason and "did not answer" in reason)


# ============================================================================
# Review fix pass, finding 15: the fixed 10s readiness wait killed
# `mlx_lm.server`'s own download-before-bind on every first use; the wait
# must scale with the model's size and never mistake "still alive, still
# loading" for "gave up and must be killed" -- and a child that quit on
# its own must surface its stderr instead of a generic timeout sentence.
# ============================================================================

@test
def test_startup_timeout_for_size_scales_with_model_size(ctx: Ctx):
    from halo_harness.providers.local_runtime import _startup_timeout_for_size
    ctx.check("unknown size -> the bare minimum", _startup_timeout_for_size(None, minimum=10.0) == 10.0)
    ctx.check("tiny size -> still the minimum (never shrinks below it)",
              _startup_timeout_for_size(1024, minimum=10.0) == 10.0)
    big = 500 * 1024 * 1024
    expected = big / (20 * 1024 * 1024)
    ctx.check(f"a big model scales past the minimum, got {_startup_timeout_for_size(big, minimum=10.0)}",
              _startup_timeout_for_size(big, minimum=10.0) == expected and expected > 10.0)


@test
def test_start_managed_server_accepts_a_child_that_answers_after_a_real_delay(ctx: Ctx):
    """Review fix pass (finding 15): `_wait_ready` keeps polling (never
    gives up early) while the child is demonstrably still alive and
    within its own budget -- a server that only starts answering
    `/v1/models` after a real delay must still be accepted, not treated
    as hung the instant some arbitrarily-small fixed window elapses."""
    from halo_harness.providers.local_runtime import start_managed_server
    state_dir = Path(tempfile.mkdtemp(prefix="local-runtime-delay-"))
    stub = _write_stub(_STUB_LISTENS_AFTER_DELAY)
    entry, reason = start_managed_server(model="slow-starter", runtime="llama-server",
                                          binary_argv=[sys.executable, str(stub)], model_path="/models/slow.gguf",
                                          state_dir=state_dir, startup_timeout=10.0)
    try:
        ctx.check(f"accepted despite the 1.5s delay, got reason={reason!r}", entry is not None)
    finally:
        if entry is not None:
            from halo_harness.providers.local_runtime import _terminate_pid
            _terminate_pid(entry.pid)


@test
def test_start_managed_server_reports_stderr_tail_on_early_exit(ctx: Ctx):
    """Review fix pass (finding 15): a child that quits on its own (a bad
    arg, a model it can't load) before ever answering `/v1/models` must
    surface ITS OWN stderr in the failure reason, never the generic "did
    not answer in time" sentence -- that sentence is actively misleading
    for a process that is not even running any more."""
    from halo_harness.providers.local_runtime import start_managed_server
    state_dir = Path(tempfile.mkdtemp(prefix="local-runtime-stderr-"))
    stub = _write_stub(_STUB_EXITS_WITH_STDERR)
    entry, reason = start_managed_server(model="dies-early", runtime="llama-server",
                                          binary_argv=[sys.executable, str(stub)], model_path="/models/dies.gguf",
                                          state_dir=state_dir, startup_timeout=5.0)
    ctx.check(f"start reports failure, got entry={entry!r}", entry is None)
    ctx.check(f"reason says it exited (not a timeout), got {reason!r}", reason and "exited" in reason)
    ctx.check(f"the child's own stderr text is in the reason, got {reason!r}",
              reason and "pretend model file could not be loaded" in reason)


@test
def test_stop_all_except_kept(ctx: Ctx):
    from halo_harness.providers.local_runtime import (load_registry, start_managed_server,
                                                        stop_all_managed_servers_except_kept, _terminate_pid)
    state_dir = Path(tempfile.mkdtemp(prefix="local-runtime-state-"))
    stub = _write_stub(_STUB_LISTENS)
    kept, _ = start_managed_server(model="keep-me", runtime="llama-server", binary_argv=[sys.executable, str(stub)],
                                    model_path="a.gguf", state_dir=state_dir, keep=True)
    gone, _ = start_managed_server(model="stop-me", runtime="llama-server", binary_argv=[sys.executable, str(stub)],
                                    model_path="b.gguf", state_dir=state_dir, keep=False)
    try:
        ctx.check("both started", kept is not None and gone is not None)
        stop_all_managed_servers_except_kept(state_dir=state_dir)
        remaining = {e["model"] for e in load_registry(state_dir)}
        ctx.check(f"kept entry survives, got {remaining}", remaining == {"keep-me"})
        ctx.check("the non-kept process was actually terminated", _wait_until(lambda: not _is_alive(gone.pid)))
        ctx.check("the kept process is still alive", _is_alive(kept.pid))
    finally:
        _terminate_pid(kept.pid if kept else None)
        _terminate_pid(gone.pid if gone else None)


@test
def test_find_runtime_binary_searches_the_runtimes_dir(ctx: Ctx):
    from halo_harness.providers.local_runtime import find_runtime_binary, runtimes_dir
    state_dir = Path(tempfile.mkdtemp(prefix="local-runtime-find-"))
    exe_name = "llama-server.exe" if sys.platform == "win32" else "llama-server"
    old_dir = runtimes_dir(state_dir) / "b1000"
    new_dir = runtimes_dir(state_dir) / "b2000"
    for d in (old_dir, new_dir):
        (d / "bin").mkdir(parents=True)
        (d / "bin" / exe_name).write_bytes(b"")
    import shutil
    real_which = shutil.which
    try:
        shutil.which = lambda name: None  # force the PATH lookup to miss, exercising the runtimes_dir fallback
        found = find_runtime_binary("llama-server", state_dir=state_dir)
    finally:
        shutil.which = real_which
    ctx.check(f"found the NEWER version directory, got {found}", found is not None and "b2000" in found[0])


@test
def test_find_runtime_binary_mlx_lm_shape(ctx: Ctx):
    from halo_harness.providers.local_runtime import find_runtime_binary
    found = find_runtime_binary("mlx_lm")
    ctx.check(f"either not found, or the documented python -m shape, got {found}",
              found is None or found == [sys.executable, "-m", "mlx_lm.server"])


@test
def test_runtime_for_format(ctx: Ctx):
    from halo_harness.providers.local_runtime import runtime_for_format
    ctx.check("gguf always maps to llama-server", runtime_for_format("gguf") == "llama-server")
    expected_mlx = "mlx_lm" if sys.platform == "darwin" else None
    ctx.check(f"safetensors maps to mlx_lm only on darwin, got {runtime_for_format('safetensors')!r}",
              runtime_for_format("safetensors") == expected_mlx)


# ============================================================================
# Review fix pass, finding 2: exit-time stop must never touch an entry a
# DIFFERENT process started, and must never signal a pid the OS has since
# reused for something unrelated (it still drops the stale record).
# ============================================================================

@test
def test_stop_all_except_kept_leaves_another_process_entry_alone(ctx: Ctx):
    from halo_harness.providers.local_runtime import (load_registry, save_registry, start_managed_server,
                                                        stop_all_managed_servers_except_kept, _terminate_pid)
    state_dir = Path(tempfile.mkdtemp(prefix="local-runtime-state-"))
    stub = _write_stub(_STUB_LISTENS)
    entry, _ = start_managed_server(model="other-session.gguf", runtime="llama-server",
                                      binary_argv=[sys.executable, str(stub)], model_path="other-session.gguf",
                                      state_dir=state_dir)
    try:
        ctx.check("start succeeded", entry is not None)
        # Simulate "a DIFFERENT halo process recorded this" -- this test
        # process is in fact the one that spawned it, but the registry
        # entry's own owner fields say otherwise, exactly like reading a
        # second session's live entry cold.
        entries = load_registry(state_dir)
        entries[0]["owner_pid"] = entries[0]["owner_pid"] + 1
        entries[0]["owner_start"] = "not-this-process"
        save_registry(state_dir, entries)
        stop_all_managed_servers_except_kept(state_dir=state_dir)
        ctx.check("the entry is still in the registry, untouched",
                  [e["model"] for e in load_registry(state_dir)] == ["other-session.gguf"])
        ctx.check("the process was never signalled -- still alive", _is_alive(entry.pid))
    finally:
        if entry is not None:
            _terminate_pid(entry.pid)


@test
def test_stop_all_except_kept_drops_stale_pid_without_signalling(ctx: Ctx):
    from halo_harness.providers.local_runtime import (load_registry, save_registry, start_managed_server,
                                                        stop_all_managed_servers_except_kept, _terminate_pid)
    state_dir = Path(tempfile.mkdtemp(prefix="local-runtime-state-"))
    stub = _write_stub(_STUB_LISTENS)
    entry, _ = start_managed_server(model="stale-pid.gguf", runtime="llama-server",
                                      binary_argv=[sys.executable, str(stub)], model_path="stale-pid.gguf",
                                      state_dir=state_dir)
    try:
        ctx.check("start succeeded", entry is not None)
        # This process IS the recorded owner (so it's eligible to stop),
        # but the server's own recorded start time no longer matches --
        # exactly what a pid the OS reused for something else looks like.
        entries = load_registry(state_dir)
        entries[0]["proc_start"] = "a-start-time-that-will-never-match"
        save_registry(state_dir, entries)
        stop_all_managed_servers_except_kept(state_dir=state_dir)
        ctx.check("the stale entry was dropped from the registry", load_registry(state_dir) == [])
        ctx.check("the real process was never signalled -- still alive", _is_alive(entry.pid))
    finally:
        if entry is not None:
            _terminate_pid(entry.pid)


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
