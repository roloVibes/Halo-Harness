"""halo_harness.selfexec -- how Halo starts its own Python, never importing from the working folder (3.6.0.0 R10).

`python -m halo_harness ...` puts the CURRENT FOLDER first on `sys.path`. Started from a project that holds a
`halo_harness/` folder (a checkout of this repo), the child imported that copy instead of the installation ("Studio
did not start"); a project with a `json.py` or `yaml.py` beside its code had that code run the moment Halo started a
helper there. Every Halo-python child is started by `python_argv`:

    Python 3.11+   [python, -P, (-u,) -m, <module>]     -P: the unsafe path (the current folder) is never prepended
    Python 3.10    [python, (-u,) -c, BOOT(<module>)]   the bootstrap drops the '' entry `-c` put first, then runs
                                                        the module with runpy (nothing is imported before that but
                                                        what the interpreter's own start-up already loaded)

`PYTHONSAFEPATH` is NOT set in the child's environment: it would be inherited by every command the child runs for the
user (a tool command's own `python -m mypkg` in a project would stop finding the project). `-I`/`-E` are not used
either: Halo children rely on the variables Halo sets for them (the home, the owner watch, provider keys). The flag
and the bootstrap act on this one interpreter only.
"""

from __future__ import annotations

import copy
import os
import sys
from pathlib import Path

BOOT = ("import sys; sys.path[:1] = [] if sys.path and sys.path[0] in ('', '.') else sys.path[:1]; "
        "import runpy; runpy.run_module({module!r}, run_name='__main__', alter_sys=True)")  # one line: unit files too


def python_argv(module: str = "halo_harness", *, unbuffered: bool = False, python: str = "") -> list:
    """The argv head that runs `module` as `python -m` does, from the installation only."""
    exe = python or sys.executable
    flags = ["-u"] if unbuffered else []
    if sys.version_info >= (3, 11):
        return [exe, "-P", *flags, "-m", module]
    return [exe, *flags, "-c", BOOT.format(module=module)]


def persisted_argv(module: str = "halo_harness", *, python: str = "") -> list:
    """The command line Halo WRITES INTO A FILE that outlives this run (an MCP entry in a user's config, a service unit,
    a logon task): it may be run by another Python of the install, so it must work on every supported one (3.10 has
    no `-P`) and still never import from the working folder -- the one-line bootstrap, on every version."""
    return [python or sys.executable, "-c", BOOT.format(module=module)]


def _norm(p: str) -> str:
    return os.path.normcase(os.path.abspath(p)) if p else ""


def _site_dirs() -> set:
    import site
    out = set()
    try:
        out |= {_norm(p) for p in site.getsitepackages()}
    except Exception:
        pass
    try:
        out.add(_norm(site.getusersitepackages()))
    except Exception:
        pass
    return out


def is_self(args) -> bool:
    """`args` starts one of Halo's own Python children (the shapes `python_argv` makes)."""
    if not isinstance(args, (list, tuple)) or len(args) < 3:
        return False
    toks = [str(a) for a in args[1:6]]
    if "-m" in toks:
        i = toks.index("-m")
        return "-P" in toks[:i] and i + 1 < len(toks) and toks[i + 1].split(".")[0] == "halo_harness"
    return "-c" in toks and any("run_module('halo_harness" in t for t in toks)


def fix_kw(args, kw: dict) -> dict:
    """The child must import THIS installation: with the working folder off its path, a package that is not in a
    site-packages folder (a checkout run from its folder, the test suite, an editable install) is passed on by
    PYTHONPATH, ahead of anything else. One installed in site-packages is on the child's path already: no change."""
    if not is_self(args):
        return kw
    root = _norm(str(Path(__file__).resolve().parent.parent))
    env = kw.get("env") if isinstance(kw.get("env"), dict) else None
    pp = (env if env is not None else os.environ).get("PYTHONPATH", "")
    if root in _site_dirs() or (pp.split(os.pathsep)[:1] and _norm(pp.split(os.pathsep)[0]) == root):
        return kw
    env = copy.copy(env) if env is not None else dict(os.environ)  # copy keeps its kind (closing.Unmarked)
    env["PYTHONPATH"] = root + (os.pathsep + pp if pp else "")
    return dict(kw, env=env)


def safe_flags() -> list:
    """The flags alone (a config that names the interpreter and its args separately: an MCP server entry)."""
    return ["-P"] if sys.version_info >= (3, 11) else []
