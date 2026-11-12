"""halo_harness.subprocess_safe -- the standard `subprocess` module with one change (Halo 3.4.1.2, PACKS-4): a program
named by a bare name (`git`, `netsh`, `taskkill` ...) is resolved to its absolute path over the PATH folders, never the
current folder, before it is started.

On Windows, CreateProcess looks for a bare name in the parent's current folder before System32 and PATH, so a repo
holding `git.exe` ran it the moment Halo asked git for the branch. Two parts close that:

1. `guard_cwd_search()` sets `NoDefaultCurrentDirectoryInExePath=1` in this process (halo_harness/__init__.py runs it
   first, so the console script, `python -m halo_harness`, headless sessions, Studio, the host and pack CLIs all have it
   before any child starts, and every child inherits it);
2. every module of the package and the shipped packs imports this module as its `subprocess`
   (`from halo_harness import subprocess_safe as subprocess`), so `run` / `Popen` / `call` / `check_call` /
   `check_output` resolve a bare argv[0] with `exe()`. tests/test_bare_spawns.py fails on a module that imports the
   standard module instead.

A test that replaced the standard function (`subprocess.run = fake`) still gets the call, unchanged. A name not found
on PATH is passed as it was (the first part keeps Windows from looking in the current folder for it). Anything else is
the standard module's (`__getattr__`).
"""

from __future__ import annotations

import os
import subprocess as _sp
import sys
from subprocess import DEVNULL, PIPE, STDOUT, CalledProcessError, CompletedProcess, SubprocessError, TimeoutExpired  # noqa: F401
from typing import Optional

STDLIB_POPEN = _sp.Popen
_ORIG = {"run": _sp.run, "call": _sp.call, "check_call": _sp.check_call, "check_output": _sp.check_output,
         "Popen": _sp.Popen}
_cache: dict = {}


def guard_cwd_search() -> None:
    """Windows: CreateProcess (and Python 3.12's shutil.which) skip the current folder for a bare program name."""
    if sys.platform == "win32":
        os.environ.setdefault("NoDefaultCurrentDirectoryInExePath", "1")


def _bare(name) -> bool:
    return (isinstance(name, str) and bool(name) and not any(ch in name for ch in "/\\:")
            and not os.path.isabs(name))


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
        super().__init__(resolve(args, kw), *a, **kw)


def __getattr__(name: str):
    return getattr(_sp, name)
