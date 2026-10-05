"""halo_harness.providers.local_runtime -- Halo 2.0.3 round 5c (brief item
3, "use it, option A"): starts/stops a managed `llama-server`/`mlx_lm`
child process serving one file-backed model on a free loopback port, and
the on-disk registry (`~/.halo/run/local-servers.json`) that survives
across `halo` invocations so `halo local stop <model>` (a FRESH process)
can still find and kill it by pid.

Never put on PATH, never bound beyond `127.0.0.1` (every other local
server/probe in this codebase is loopback-first; the managed runtime
follows the same default). `headless.py`/`controller.py` call
`stop_all_managed_servers_except_kept` from the same `finally:`/`atexit`
spots that already stop background Bash jobs and a `cc:` subprocess, so a
served model never outlives the `halo` process that started it unless
`keep: true` was set.
"""

from __future__ import annotations

import contextlib
import json
import logging
import os
import socket
import subprocess
import sys
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

log = logging.getLogger("bridge")

_READY_POLL_INTERVAL_S = 0.2


@dataclass(frozen=True)
class ManagedServer:
    model: str
    runtime: str  # "llama-server" | "mlx_lm"
    pid: int
    port: int
    base_url: str
    started: str
    keep: bool
    # Review fix pass (finding 2): who started it and what it actually is,
    # recorded so a LATER stop -- this process at exit, or a fresh `halo
    # local stop`/`halo` invocation reading the registry file cold -- can
    # tell "mine", "another session's", and "stale, pid now reused by
    # something unrelated" apart before signalling anything.
    owner_pid: int = -1
    owner_start: "Optional[str]" = None  # bg_run.process_start_time(owner_pid) at creation
    proc_start: "Optional[str]" = None  # bg_run.process_start_time(pid) at creation
    cmdline: list = field(default_factory=list)


def runtimes_dir(state_dir) -> Path:
    return Path(state_dir) / "runtimes"


def registry_path(state_dir) -> Path:
    return Path(state_dir) / "run" / "local-servers.json"


def load_registry(state_dir) -> "list[dict]":
    try:
        data = json.loads(registry_path(state_dir).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    return data if isinstance(data, list) else []


def save_registry(state_dir, entries: "list[dict]") -> None:
    path = registry_path(state_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + f".tmp{os.getpid()}")
    tmp.write_text(json.dumps(entries, indent=2) + "\n", encoding="utf-8")
    os.replace(tmp, path)


@contextlib.contextmanager
def _registry_lock(state_dir, *, timeout: float = 5.0):
    """Review fix pass (finding 2), last bullet: "serialize registry
    writes with a lock file" -- a plain create-exclusive lock FILE beside
    the registry (this project has no existing cross-platform flock/
    msvcrt helper and declines the psutil dependency the review's own fix
    text offers as an alternative), so two `halo` processes racing a
    start/stop never do load-modify-save over each other and silently
    drop one of their entries. `O_CREAT|O_EXCL` is atomic on every OS this
    project supports. A lock file older than `timeout` is assumed
    abandoned by a process that crashed between creating and removing it,
    and is stolen rather than waited on forever; giving up at the
    deadline and proceeding WITHOUT the lock (never raising, never
    hanging) is the same degrade-rather-than-block posture every other
    best-effort registry helper in this module already has."""
    path = registry_path(state_dir).with_name(registry_path(state_dir).name + ".lock")
    path.parent.mkdir(parents=True, exist_ok=True)
    deadline = time.monotonic() + timeout
    held = False
    while True:
        try:
            fd = os.open(str(path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            os.close(fd)
            held = True
            break
        except FileExistsError:
            try:
                if time.time() - path.stat().st_mtime > timeout:
                    path.unlink(missing_ok=True)
                    continue
            except OSError:
                pass
            if time.monotonic() >= deadline:
                break
            time.sleep(0.05)
        except OSError:
            break
    try:
        yield
    finally:
        if held:
            try:
                path.unlink(missing_ok=True)
            except OSError:
                pass


def _owner_fingerprint() -> "tuple[int, Optional[str]]":
    """This process's own `(pid, start_time)` -- recorded on every entry
    it creates (see `ManagedServer.owner_pid`/`owner_start`'s own
    docstring)."""
    from halo_harness.bg_run import process_start_time
    pid = os.getpid()
    return pid, process_start_time(pid)


def _entry_owned_by_this_process(entry: dict) -> bool:
    """True only for an entry recorded by the SAME running process asking
    the question -- review fix pass finding 2: `stop_all_managed_servers_
    except_kept` must stop only servers THIS process started, never a
    second session's managed server or a stale entry a crashed/closed one
    left behind. `halo local stop <model>` stays the explicit, user-
    directed way to stop any other entry by name. A bare pid match is not
    enough (the OS reuses pids across separate processes), so a recorded
    `owner_start` must also agree with this process's own start time right
    now -- `None` on either side (a pre-upgrade entry with no owner
    fields, or a platform `bg_run.process_start_time` can't read) can't
    disprove a match, so it is NOT treated as a refusal, the same
    tolerant default `bg_run.is_our_process` already uses for the
    identical pid-reuse problem."""
    if entry.get("owner_pid") != os.getpid():
        return False
    recorded = entry.get("owner_start")
    if not recorded:
        return True
    from halo_harness.bg_run import process_start_time
    mine = process_start_time(os.getpid())
    return mine is None or mine == recorded


def _entry_process_matches(entry: dict) -> bool:
    """Best-effort "is `entry['pid']` still the SAME OS process that was
    recorded" check, run right before signalling it -- review fix pass
    finding 2: "a stale entry gets its pid killed whatever process now
    owns it". `recorded`/`current` both unknown or equal can't disprove
    a match (same tolerant default as `_entry_owned_by_this_process`);
    only a confirmed MISMATCH says "do not signal this pid"."""
    recorded = entry.get("proc_start")
    if not recorded:
        return True
    from halo_harness.bg_run import process_start_time
    current = process_start_time(entry.get("pid"))
    return current is None or current == recorded


def find_free_port() -> int:
    """Bind to port 0 for an OS-assigned free port, then release it -- the
    same small-TOCTOU-race-accepted pattern `tests/helpers/mock_openai.
    free_port` already uses for test servers."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def llama_server_argv(binary_argv: list, *, model_path, port: int, context_length: Optional[int] = None) -> list:
    """Brief item 3's own exact flags: `-m <file> -c <fit> -ngl 99 -fa on
    --port <p> --host 127.0.0.1`. `-c` is omitted (llama-server's own
    documented default, "0, meaning load from the model" -- LOCAL-MODELS-
    RESEARCH.md section 8) only when `context_length` isn't known."""
    argv = list(binary_argv) + ["-m", str(model_path)]
    if context_length:
        argv += ["-c", str(context_length)]
    argv += ["-ngl", "99", "-fa", "on", "--port", str(port), "--host", "127.0.0.1"]
    return argv


def mlx_lm_server_argv(binary_argv: list, *, model_path, port: int) -> list:
    """Brief item 3's own exact flags: `--model <dir> --port <p>` -- no
    `--host` (GPU-RESEARCH.md section 7: mlx_lm.server's own flags are
    UNCONFIRMED at the exact-name level this round; adding an unconfirmed
    flag risks the whole spawn failing outright, so this follows the
    brief's literal example rather than guessing one)."""
    return list(binary_argv) + ["--model", str(model_path), "--port", str(port)]


def find_runtime_binary(runtime: str, *, state_dir=None) -> "Optional[list]":
    """The argv PREFIX to invoke `runtime` ("llama-server" | "mlx_lm"), or
    `None` when not found. `mlx_lm` installs as a Python package (`pip
    install mlx-lm`, GPU-RESEARCH.md section 7), never a standalone PATH
    binary -- "found" means `import mlx_lm` would succeed, invoked as
    `python -m mlx_lm.server`. `llama-server` is checked on PATH first,
    then under `~/.halo/runtimes/<version>/` (newest version first, by
    name -- the directory name IS the release tag this round's fetcher
    names it after) for a file literally named `llama-server`(`.exe`) --
    a recursive search rather than one hard-coded internal path, since the
    official release archive's own internal layout per OS was not
    independently confirmed this round."""
    if runtime == "mlx_lm":
        import importlib.util
        return [sys.executable, "-m", "mlx_lm.server"] if importlib.util.find_spec("mlx_lm") is not None else None
    if runtime != "llama-server":
        return None
    import shutil
    on_path = shutil.which("llama-server")
    if on_path:
        return [on_path]
    if state_dir is None:
        from halo_harness.config.paths import bridge_home
        state_dir = bridge_home()
    root = runtimes_dir(state_dir)
    if not root.is_dir():
        return None
    exe_name = "llama-server.exe" if sys.platform == "win32" else "llama-server"
    for version_dir in sorted((p for p in root.iterdir() if p.is_dir()), reverse=True):
        for candidate in sorted(version_dir.rglob(exe_name)):
            if candidate.is_file():
                return [str(candidate)]
    return None


def runtime_for_format(fmt: str) -> Optional[str]:
    """Which managed runtime serves a `providers.local_model_dirs.
    LocalModelFile.format` -- `"gguf"` -> `llama-server` everywhere;
    `"safetensors"`/`"mlx"` -> `mlx_lm`, Apple Silicon only (brief:
    llama-server serves GGUF, mlx_lm serves safetensors-shaped folders);
    `None` when nothing in this codebase manages a safetensors folder on
    this platform (option B -- `halo local import` -- may still apply)."""
    if fmt == "gguf":
        return "llama-server"
    if fmt in ("safetensors", "mlx") and sys.platform == "darwin":
        return "mlx_lm"
    return None


def _wait_ready(base_url: str, *, timeout: float) -> bool:
    from halo_harness.providers.huggingface_local_probe import probe_models_endpoint
    deadline = time.monotonic() + timeout
    while True:
        if probe_models_endpoint(base_url, timeout=min(2.0, timeout)) is not None:
            return True
        if time.monotonic() >= deadline:
            return False
        time.sleep(_READY_POLL_INTERVAL_S)


def start_managed_server(*, model: str, runtime: str, binary_argv: list, model_path, context_length=None,
                          port: Optional[int] = None, keep: bool = False, state_dir=None,
                          startup_timeout: float = 10.0) -> "tuple[Optional[ManagedServer], Optional[str]]":
    """Spawns the child process, waits for `/v1/models` to answer, records
    it in the registry, and registers it in-process as `hf:local/<model>`
    for THIS session (`providers.huggingface_local_resolve.
    register_managed_server`). `(None, reason)` on any failure (unknown
    runtime, the binary itself failed to spawn, or it never answered
    within `startup_timeout` -- the half-started process is terminated
    before returning)."""
    if state_dir is None:
        from halo_harness.config.paths import bridge_home
        state_dir = bridge_home()
    port = port if port is not None else find_free_port()
    if runtime == "llama-server":
        argv = llama_server_argv(binary_argv, model_path=model_path, port=port, context_length=context_length)
    elif runtime == "mlx_lm":
        argv = mlx_lm_server_argv(binary_argv, model_path=model_path, port=port)
    else:
        return None, f"unknown runtime {runtime!r}"
    try:
        proc = subprocess.Popen(argv, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, stdin=subprocess.DEVNULL)
    except OSError as e:
        return None, f"failed to start {runtime}: {e}"
    # FIX PASS (Kali/WSL live run): registered BEFORE `_wait_ready` so even
    # the "never answered in time" cleanup path below reaps it properly
    # (see `_terminate_pid`'s own docstring) instead of leaving a zombie.
    _register_popen(proc)
    base_url = f"http://127.0.0.1:{port}/v1"
    if not _wait_ready(base_url, timeout=startup_timeout):
        _terminate_pid(proc.pid)
        return None, f"{runtime} did not answer {base_url}/models within {startup_timeout:.0f}s"
    from halo_harness.bg_run import process_start_time
    owner_pid, owner_start = _owner_fingerprint()
    entry = ManagedServer(model=model, runtime=runtime, pid=proc.pid, port=port, base_url=base_url,
                           started=datetime.now(timezone.utc).isoformat(), keep=bool(keep),
                           owner_pid=owner_pid, owner_start=owner_start,
                           proc_start=process_start_time(proc.pid), cmdline=list(argv))
    # The registry FILE is the one source of truth for "which hf:local/*
    # entry is this, for this session" -- `providers.huggingface_local_
    # resolve.resolve_local_server` reads it directly (its own fallback
    # after a configured manual entry and a live auto-detect probe), so
    # no separate in-memory registration step is needed here, and a
    # SEPARATE `halo` process started after this one can resolve it too.
    # Review fix pass (finding 2): the whole load-filter-append-save
    # sequence is now one locked transaction so a concurrent writer never
    # loses this entry (or has this entry lose one of its own).
    with _registry_lock(state_dir):
        entries = [e for e in load_registry(state_dir) if e.get("model") != model]
        entries.append(dict(entry.__dict__))
        save_registry(state_dir, entries)
    return entry, None


_POPEN_LOCK = threading.Lock()
_POPEN_HANDLES: dict = {}  # pid -> subprocess.Popen, for a server THIS process started


def _register_popen(proc) -> None:
    with _POPEN_LOCK:
        _POPEN_HANDLES[proc.pid] = proc


def _forget_popen(pid):
    with _POPEN_LOCK:
        return _POPEN_HANDLES.pop(pid, None)


def _posix_proc_state(pid) -> Optional[str]:
    """The single-character STATE field from `/proc/<pid>/stat` (Linux/
    WSL; `None` when the file doesn't exist at all -- macOS, or the
    process is already fully gone). `"Z"` means zombie: already dead in
    every way that matters except its parent hasn't `wait()`-ed on it
    yet, so sending it ANOTHER signal (SIGKILL included) accomplishes
    nothing -- only a `wait()`/`waitpid()` by the parent clears it."""
    try:
        with open(f"/proc/{pid}/stat", "r") as f:
            content = f.read()
    except OSError:
        return None
    idx = content.rfind(")")  # `comm` (2nd field) may itself contain "( )"
    if idx == -1:
        return None
    fields = content[idx + 1:].split()
    return fields[0] if fields else None


def _pid_exists(pid) -> bool:
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except OSError:
        return True  # exists but e.g. permission denied to signal it


def _terminate_pid(pid) -> None:
    """FIX PASS (live run on Kali/WSL): the stub/real runtime process is
    a CHILD of whichever process called `start_managed_server` -- on
    POSIX, a bare `SIGTERM` with no `wait()` leaves a ZOMBIE (gone in
    every practical sense, but `os.kill(pid, 0)` still reports it as
    "alive" until its parent reaps it), which made `halo local stop`
    look like it had failed. Two paths:

    - SAME process that started it (`_POPEN_HANDLES` has the real
      `Popen` handle): `terminate()` then `wait(timeout=5)` -- this
      REAPS it, no zombie possible; `kill()` + a second `wait()` if it
      ignored SIGTERM.
    - NO handle (a fresh `halo local stop` process reading the registry
      file; also Windows, which has no `waitpid`-for-an-arbitrary-pid
      concept at all): send SIGTERM, then poll `os.waitpid(pid,
      os.WNOHANG)` for ~5s (guarded for `ChildProcessError` -- this pid
      is not our child, the common case for a fresh process), and only
      escalate to SIGKILL once the grace period elapses AND the process
      is still genuinely alive (never SIGKILL a zombie -- it cannot do
      anything with another signal)."""
    import signal
    proc = _forget_popen(pid)
    if proc is not None:
        try:
            proc.terminate()
            proc.wait(timeout=5)
            return
        except Exception:
            log.debug("local_runtime: terminate() didn't reap pid %s within 5s, escalating to kill()", pid)
        try:
            proc.kill()
            proc.wait(timeout=5)
        except Exception:
            log.debug("local_runtime: kill() still didn't reap pid %s", pid, exc_info=True)
        return
    try:
        os.kill(pid, signal.SIGTERM)
    except (OSError, ProcessLookupError, TypeError):
        return
    if sys.platform == "win32":
        return  # SIGTERM on Windows already calls TerminateProcess -- no reaping concept applies
    deadline = time.monotonic() + 5.0
    while time.monotonic() < deadline:
        try:
            reaped_pid, _status = os.waitpid(pid, os.WNOHANG)
            if reaped_pid == pid:
                return
        except ChildProcessError:
            pass  # not our child -- nothing THIS process can reap; keep polling liveness below
        except OSError:
            return
        if not _pid_exists(pid):
            return
        time.sleep(0.2)
    if _pid_exists(pid) and _posix_proc_state(pid) != "Z":
        try:
            os.kill(pid, signal.SIGKILL)
        except (OSError, ProcessLookupError):
            pass


def stop_managed_server(model: str, *, state_dir=None) -> "tuple[bool, str]":
    """`halo local stop <model>` -- works from a FRESH process (reads the
    registry file, kills by recorded pid; there is no live `Popen` handle
    to rely on across invocations). This is the EXPLICIT, user-directed
    path (brief item 3, round 2 fix pass finding 2): it may stop an entry
    regardless of which process started it -- but, same as the at-exit
    sweep, it still refuses to SIGNAL a pid whose recorded start time no
    longer matches (a stale entry the OS has since reused for something
    unrelated); the stale record is still removed, just never signalled."""
    if state_dir is None:
        from halo_harness.config.paths import bridge_home
        state_dir = bridge_home()
    with _registry_lock(state_dir):
        entries = load_registry(state_dir)
        match = next((e for e in entries if e.get("model") == model), None)
        if match is None:
            return False, f"no managed server recorded for {model!r}"
        save_registry(state_dir, [e for e in entries if e.get("model") != model])
    if not _entry_process_matches(match):
        return True, (f"removed a stale record for {model!r} (pid {match.get('pid')} on port "
                       f"{match.get('port')} now belongs to a different process; nothing was signalled)")
    _terminate_pid(match.get("pid"))
    return True, f"stopped {match.get('runtime')} on port {match.get('port')}"


def stop_all_managed_servers_except_kept(state_dir=None) -> None:
    """Stopped when Halo exits unless `keep: true` (brief item 3) --
    called from `headless.py`'s print-mode `finally:`+`atexit` and
    `controller.Controller.quit()`, the same two spots that already stop
    background Bash jobs and a `cc:` subprocess. Idempotent and never
    raises -- safe to call more than once on the same exit.

    Review fix pass (finding 2): this used to stop EVERY non-kept entry,
    pid and all, with no check that the exiting process is the one that
    started it. That killed a second session's managed server out from
    under it, and killed whatever process a stale pid had been reused
    for. Now: an entry this process didn't start (`_entry_owned_by_this_
    process`) is left in the registry untouched -- only `halo local stop
    <model>` may stop those. An entry this process DID start but whose
    pid no longer matches the process recorded at creation
    (`_entry_process_matches`) is dropped from the registry WITHOUT being
    signalled. The whole load-decide-terminate-save sequence is one
    locked transaction so a concurrent writer's entry is never lost."""
    if state_dir is None:
        from halo_harness.config.paths import bridge_home
        state_dir = bridge_home()
    try:
        with _registry_lock(state_dir):
            entries = load_registry(state_dir)
            remaining = []
            for e in entries:
                if e.get("keep"):
                    remaining.append(e)
                    continue
                if not _entry_owned_by_this_process(e):
                    remaining.append(e)
                    continue
                if _entry_process_matches(e):
                    _terminate_pid(e.get("pid"))
                # else: pid was reused by an unrelated process -- drop the
                # stale entry without signalling it.
            save_registry(state_dir, remaining)
    except Exception:
        pass
