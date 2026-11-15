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


def _call(name: str, args, kw: dict):
    fn = getattr(_sp, name)
    if fn is not _ORIG[name]:  # a test replaced the standard function: it gets the call as written
        return fn(args, **kw)
    from halo_harness.selfexec import fix_kw  # 3.6.0.0 R10: Halo's own Python child imports this installation
    kw = fix_kw(args, kw)
    return fn(resolve(args, kw), **kw)


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
        # may not break away from an outer Job starts without the breakaway flag rather than not at all.
        from halo_harness import closing, selfexec
        kw = closing.before_spawn(selfexec.fix_kw(args, kw))
        try:
            super().__init__(resolve(args, kw), *a, **kw)
        except PermissionError:
            flags = int(kw.get("creationflags") or 0)
            if not (flags & closing._BREAKAWAY):
                raise
            kw = dict(kw, creationflags=flags & ~closing._BREAKAWAY)
            # The failed attempt closed the DEVNULL handle it opened but left `_devnull` naming it; a retry on the
            # same object would hand the child that closed handle ([Errno 9] Bad file descriptor). Start clean.
            self.__dict__.pop("_devnull", None)
            super().__init__(resolve(args, kw), *a, **kw)
        try:
            closing.after_spawn(self, kw)
        except Exception:
            pass


def __getattr__(name: str):
    return getattr(_sp, name)
