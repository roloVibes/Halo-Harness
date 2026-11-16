"""halo_harness.subprocess_safe -- the standard `subprocess` module with one change (Halo 3.4.1.2, PACKS-4): a program
named by a bare name (`git`, `netsh`, `taskkill` ...) is resolved to its absolute path over the PATH folders, never the
current folder, before it is started.

On Windows, CreateProcess looks for a bare name in the parent's current folder before System32 and PATH, so a repo
holding `git.exe` ran it the moment Halo asked git for the branch. Three parts close that:

1. `guard_cwd_search()` sets `NoDefaultCurrentDirectoryInExePath=1` in this process (halo_harness/__init__.py runs it
   first, so the console script, `python -m halo_harness`, headless sessions, Studio, the host and pack CLIs all have it
   before any child starts, and every child inherits it);
2. every module of the package and the shipped packs imports this module as its `subprocess`
   (`from halo_harness import subprocess_safe as subprocess`), so `run` / `Popen` / `call` / `check_call` /
   `check_output` resolve a bare argv[0] with `exe()`. tests/test_bare_spawns.py fails on a module that imports the
   standard module instead;
3. (3.6.0.0) on Windows `guard_cwd_search()` also makes `shutil.which` this module's `which` (PATH folders only):
   Python 3.10 / 3.11's own answered `.\\rg.CMD` from the current folder, and callers run the path it answers.

A test that replaced the standard function (`subprocess.run = fake`) still gets the call, unchanged. A name not found
on PATH is passed as it was (the first part keeps Windows from looking in the current folder for it). Anything else is
the standard module's (`__getattr__`).
"""

from __future__ import annotations

import os
import shutil
import subprocess as _sp
import sys
from subprocess import DEVNULL, PIPE, STDOUT, CalledProcessError, CompletedProcess, SubprocessError, TimeoutExpired  # noqa: F401
from typing import Optional

STDLIB_POPEN = _sp.Popen
_ORIG = {"run": _sp.run, "call": _sp.call, "check_call": _sp.check_call, "check_output": _sp.check_output,
         "Popen": _sp.Popen}
_cache: dict = {}
_STD_WHICH = getattr(shutil, "_halo_std_which", shutil.which)  # the standard one, also after a reload of this module
shutil._halo_std_which = _STD_WHICH


def guard_cwd_search() -> None:
    """Windows: CreateProcess skips the current folder for a bare program name, and so does `shutil.which` (3.6.0.0:
    Python 3.10 / 3.11's own put the current folder first whatever the variable says, and about 90 places run the
    path it answers: Grep's rg, Setup's halo, gh, ffmpeg ... It is this module's `which` from here on)."""
    if sys.platform == "win32":
        os.environ.setdefault("NoDefaultCurrentDirectoryInExePath", "1")
        shutil.which = which


def _bare(name) -> bool:
    return (isinstance(name, str) and bool(name) and not any(ch in name for ch in "/\\:")
            and not os.path.isabs(name))


def which(cmd, mode: int = os.F_OK | os.X_OK, path=None) -> Optional[str]:
    """`shutil.which` over the absolute PATH folders alone: never the current folder, never a relative entry (`.` or
    an empty one names the current folder). A name with a folder in it is the standard function's."""
    if not _bare(cmd):
        return _STD_WHICH(cmd, mode, path)
    path = os.environ.get("PATH", os.defpath) if path is None else os.fsdecode(path)
    names = [cmd]
    if sys.platform == "win32":
        exts = [e for e in os.environ.get("PATHEXT", ".COM;.EXE;.BAT;.CMD").split(";") if e]
        # as Python 3.12's own: the name as given only when its ending is in PATHEXT (or X_OK is not asked for)
        direct = not (mode & os.X_OK) or any(cmd.upper().endswith(e.upper()) for e in exts)
        names = ([cmd] if direct else []) + [cmd + e for e in exts]
    for folder in path.split(os.pathsep):
        folder = folder.strip().strip('"')
        if not folder or not os.path.isabs(folder):
            continue
        for n in names:
            cand = os.path.join(folder, n)
            if os.path.exists(cand) and os.access(cand, mode) and not os.path.isdir(cand):
                return cand
    return None


def exe(name: str) -> str:
    """The absolute path of program `name` from a PATH folder (never `""`, `.` or another relative folder, which name
    the current one); `name` itself when it is not bare or not found."""
    if not _bare(name):
        return name
    path = os.environ.get("PATH", os.defpath)
    key = (name, path, os.environ.get("PATHEXT", ""))
    if key in _cache:
        return _cache[key]
    exts = [""]
    if sys.platform == "win32":
        exts = ([""] if os.path.splitext(name)[1] else []) + \
            [e.lower() for e in os.environ.get("PATHEXT", ".COM;.EXE;.BAT;.CMD").split(";") if e]
    found: Optional[str] = None
    for folder in path.split(os.pathsep):
        folder = folder.strip().strip('"')
        if not folder or not os.path.isabs(folder):
            continue
        for ext in exts:
            cand = os.path.join(folder, name + ext)
            if os.path.isfile(cand) and (sys.platform == "win32" or os.access(cand, os.X_OK)):
                found = cand
                break
        if found:
            break
    _cache[key] = found or name
    return _cache[key]


def resolve(args, kw: dict):
    """`args` with a bare argv[0] resolved (a list or tuple, no shell, no `executable=`); anything else as it is."""
    if kw.get("shell") or kw.get("executable") or not isinstance(args, (list, tuple)) or not args:
        return args
    first = exe(args[0]) if isinstance(args[0], str) else args[0]
    return args if first == args[0] else type(args)([first, *args[1:]])


class Probe(dict):
    """An environment for a bounded, read-only look Halo makes for itself (the `ps` identity look where there is no
    /proc): never a spawn of the closing procedure, so it starts no reaper and marks nothing spawned (3.6.0.1). Never
    for a run that executes the person's programs (a login shell, a tool)."""


def _call(name: str, args, kw: dict):
    fn = getattr(_sp, name)
    if fn is not _ORIG[name]:  # a test replaced the standard function: it gets the call as written
        return fn(args, **kw)
    if isinstance(kw.get("env"), Probe):
        return fn(resolve(args, kw), **kw)
    from halo_harness import closing
    from halo_harness.selfexec import fix_kw  # 3.6.0.0 R10: Halo's own Python child imports this installation
    # 3.6.0.0 fx: inside the closing procedure like a Popen: the child carries this tree's marker even in an
    # environment the caller built, and it counts as spawned (POSIX: the reaper starts, a close runs the marker scan)
    kw = closing.before_spawn(fix_kw(args, kw))
    env = kw.get("env")
    if not closing.is_kept_env(env):
        closing.note_spawn()
    # 3.6.0.1: on Windows through Popen (below), so the child joins this process's Job as a Popen child does and a
    # hard kill of this Halo ends it too. Never the person's editor (a scrubbed env) or a kept one: the strict Job
    # forbids leaving it, so they would end with Halo.
    if os.name == "nt" and not isinstance(env, closing.Unmarked) and not closing.is_kept_env(env):
        return _WIN[name](args, **kw)
    return fn(resolve(args, kw), **kw)


def _win_run(args, *, input=None, capture_output=False, timeout=None, check=False, **kw):
    """CPython's subprocess.run, with the child started by this module's Popen (Windows only). Every argument case
    answers as CPython's does, its ValueErrors included (3.6.0.1)."""
    if input is not None:
        if kw.get("stdin") is not None:
            raise ValueError("stdin and input arguments may not both be used.")
        kw["stdin"] = _sp.PIPE
    if capture_output:
        if kw.get("stdout") is not None or kw.get("stderr") is not None:
            raise ValueError("stdout and stderr arguments may not be used with capture_output.")
        kw["stdout"] = kw["stderr"] = _sp.PIPE
    with Popen(args, **kw) as p:
        try:
            out, err = p.communicate(input, timeout=timeout)
        except _sp.TimeoutExpired as exc:
            p.kill()
            exc.stdout, exc.stderr = p.communicate()
            raise
        except BaseException:
            p.kill()
            raise
        code = p.poll()
    if check and code:
        raise _sp.CalledProcessError(code, p.args, output=out, stderr=err)
    return _sp.CompletedProcess(p.args, code, out, err)


def _win_call(args, *, timeout=None, **kw):
    """CPython's subprocess.call: Popen and wait (no pipes read; `input`, `check` are Popen's TypeError there too)."""
    with Popen(args, **kw) as p:
        try:
            return p.wait(timeout=timeout)
        except BaseException:
            p.kill()
            raise


def _win_check_call(args, **kw):
    code = _win_call(args, **kw)
    if code:
        raise _sp.CalledProcessError(code, args)
    return 0


def _win_check_output(args, *, timeout=None, **kw):
    """CPython's subprocess.check_output: an explicit input=None is an empty input (a closed pipe, never the
    terminal's own stdin), and stdout= / check= are refused."""
    for name in ("stdout", "check"):
        if name in kw:
            raise ValueError(f"{name} argument not allowed, it will be overridden.")
    if "input" in kw and kw["input"] is None:
        text = kw.get("universal_newlines") or kw.get("text") or kw.get("encoding") or kw.get("errors")
        kw["input"] = "" if text else b""
    return _win_run(args, stdout=_sp.PIPE, timeout=timeout, check=True, **kw).stdout


_WIN = {"run": _win_run, "call": _win_call, "check_call": _win_check_call, "check_output": _win_check_output}


def run(args, **kw):
    return _call("run", args, kw)


def call(args, **kw):
    return _call("call", args, kw)


def check_call(args, **kw):
    return _call("check_call", args, kw)


def check_output(args, **kw):
    return _call("check_output", args, kw)


class Popen(_sp.Popen):
    """`subprocess.Popen` with argv[0] resolved; a test's replacement of the standard class gets the call as written."""

    def __new__(cls, args, *a, **kw):
        if _sp.Popen is not _ORIG["Popen"]:
            return _sp.Popen(args, *a, **kw)
        return super().__new__(cls)

    def __init__(self, args, *a, **kw):
        # 3.6.0.0 R10 (closing.py): the child carries this tree's HALO_OWNER marker even in an environment the caller
        # built, joins this process's Job object on Windows (unless a person asked to keep it), and a kept spawn that
        # may not break away from an outer Job starts from outside every Job (closing.start_outside_job); when even
        # that cannot be done it starts inside that Job and Halo says so in one line (never a silent pretence).
        from halo_harness import closing, selfexec
        kw = closing.before_spawn(selfexec.fix_kw(args, kw))
        try:
            if (os.name == "nt" and int(kw.get("creationflags") or 0) & closing._BREAKAWAY
                    and not closing.breakaway_frees()):  # 3.6.0.0 fx: a Job would hold it silently: as if refused
                raise PermissionError("a Job object this process is in holds what it starts")
            super().__init__(resolve(args, kw), *a, **kw)
        except PermissionError:
            flags = int(kw.get("creationflags") or 0)
            if not (flags & closing._BREAKAWAY):
                raise
            # The failed attempt closed the DEVNULL handle it opened but left `_devnull` naming it; a retry on the
            # same object would hand the child that closed handle ([Errno 9] Bad file descriptor). Start clean.
            self.__dict__.pop("_devnull", None)
            kept = closing.is_kept_env(kw.get("env"))
            if kept and not a:  # an outer Job forbids leaving it: a kept spawn starts from outside every Job
                pid = closing.start_outside_job(resolve(args, kw), kw)
                if pid is not None:  # started out there: never a second time in here, even if it has ended
                    self._stand_for(args, pid)
                    return
            kw = dict(kw, creationflags=flags & ~closing._BREAKAWAY)
            super().__init__(resolve(args, kw), *a, **kw)
            if kept:
                closing.say_held_in_job(self.pid, args, kw.get("env"))
        try:
            closing.after_spawn(self, kw)
        except Exception:
            pass

    def _stand_for(self, args, pid: int) -> None:
        """Windows: this Popen stands for process `pid`, started elsewhere (closing.start_outside_job): pid, poll,
        wait, terminate and kill work on it through a handle opened now; it has no pipes. When no handle opens (it
        has already ended) or its pid is unknown, it stands for a finished process (exit code not known: 0)."""
        import _winapi
        handle = None
        if pid:
            try:  # SYNCHRONIZE | PROCESS_QUERY_LIMITED_INFORMATION | PROCESS_TERMINATE
                handle = _winapi.OpenProcess(0x00100000 | 0x1000 | 0x0001, False, int(pid))
            except OSError:
                handle = None
        self.args, self.pid, self.returncode = args, int(pid), (None if handle else 0)
        self.stdin = self.stdout = self.stderr = None
        self.encoding = self.errors = None
        self.text_mode, self.pipesize = False, -1
        self._sigint_wait_secs, self._closed_child_pipe_fds = 0.25, True
        self._input, self._communication_started = None, False
        self._handle, self._child_created = (_sp.Handle(handle) if handle else None), bool(handle)


def start_kept(args, *, what: str, shown=None, **kw):
    """Start a program a person asked to outlive this process, in the ledger as kept (closing.start_kept); a pack's
    way to say so through `halo_harness.ext.subprocess_safe`."""
    from halo_harness import closing
    return closing.start_kept(args, what=what, shown=shown, **kw)


def __getattr__(name: str):
    return getattr(_sp, name)
