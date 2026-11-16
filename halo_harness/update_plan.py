"""halo_harness.update_plan -- what `halo update` and `/update` hand to the standalone updater, and how it starts
(Halo 3.6.0.0 R13; the updater is update_runner.py).

    expectation(target, channel, avail, before)  what `halo --version` must answer after the install
    previous_install(kind, before, current_cmd, lock)  the command that puts back what is installed now: the exact
                                                  spec (a git install's commit, a checkout's commit) and a lock of
                                                  the packages of this environment (`<state>/run/update-previous.lock`)
    freeze_lock(path)                             that lock, from this environment's own package metadata
    build_plan(...)                               the plan file's content
    outside_python()                              a Python that is NOT the environment being replaced
    launch(plan)                                  writes the runner and the plan under `<state>/run/` and starts it:
                                                  POSIX in the foreground (this process becomes the updater: exec);
                                                  Windows in its own window once this halo has exited (a running
                                                  halo.exe holds the files the install replaces)
    last_result(state_dir) / mark_seen(...)       the outcome the updater wrote, for the next `halo update`
"""
from __future__ import annotations

import json
import os
import re
import shutil
import sys
from pathlib import Path
from typing import Optional

RUN_DIR = "run"
RUNNER_NAME = "update_runner.py"
PLAN_NAME = "update-plan.json"
RESULT_NAME = "update-result.json"
LOCK_NAME = "update-previous.lock"
LOG_NAME = "update.log"
RUN_LOG_NAME = "update-run.log"  # this run's lines only: the Windows window (`--watch`) shows them
WINDOWS_PAUSE_S = 15.0
_HEX_RE = re.compile(r"^[0-9a-f]{7,40}$")
_CONSTRAINT_RE = re.compile(r'(--constraints?\s+)("[^"]*"|[^\s"]+)')


def _state(state_dir=None) -> Path:
    if state_dir is not None:
        return Path(state_dir)
    from halo_harness.config.paths import bridge_home
    return bridge_home()


def run_dir(state_dir=None) -> Path:
    return _state(state_dir) / RUN_DIR


def tag_version(ref: Optional[str]) -> Optional[str]:
    """`v3.5.0.1` -> `3.5.0.1`; None for anything that is not a release tag."""
    from halo_harness.update import _TAG_RE
    return ref[1:] if isinstance(ref, str) and _TAG_RE.match(ref) else None


def version_key(version: Optional[str]) -> "Optional[tuple]":
    """`3.5.0.1` -> (3, 5, 0, 1), padded to four parts; None when it is not a plain dotted version."""
    parts = str(version or "").lstrip("v").split(".")
    if not parts or not all(p.isdigit() for p in parts):
        return None
    return tuple(int(p) for p in (parts + ["0"] * 4)[:4])


def expectation(target: Optional[str], channel: Optional[str], avail: Optional[dict], before: dict) -> dict:
    """What the new install's `halo --version` must answer: a release tag's version, a commit's sha, or (the main
    line, which may move while the install runs) anything but the commit installed now."""
    avail = avail or {}
    version = tag_version(target)
    if version:
        return {"version": version, "label": version}
    if target and _HEX_RE.match(target.lower()):
        return {"commit": target.lower()[:7], "label": target.lower()[:7]}
    if target:
        return {"label": target}
    if channel == "main" and avail.get("commit"):
        now = before.get("commit")
        return {"not_commit": now if now and now != avail["commit"] else None,
                "label": f"{avail.get('ref') or 'main'} ({avail['commit']})"}
    return {"label": "the newest"}


def freeze_lock(path: Path) -> Optional[Path]:
    """`name==version` for every package of this environment but halo-harness itself (it is installed from its
    spec): the constraints that put the same dependencies back."""
    try:
        import importlib.metadata as im
        from halo_harness.update import DIST_NAME
        seen: dict = {}
        for dist in im.distributions():
            name = (dist.metadata.get("Name") or "").strip()
            key = re.sub(r"[-_.]+", "-", name).lower()
            if not name or not dist.version or key == DIST_NAME or key in seen:
                continue
            seen[key] = f"{name}=={dist.version}"
        if not seen:
            return None
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("# what was installed before `halo update` (update_plan.freeze_lock)\n"
                        + "\n".join(seen[k] for k in sorted(seen)) + "\n", encoding="utf-8")
        return path
    except Exception:
        return None


def _swap_lock(cmd: str, lock: Optional[str]) -> str:
    """`cmd` with its dependency pin pointed at `lock` (uv's `--constraints`, pip's and pipx's `--constraint`)."""
    if not lock or not cmd:
        return cmd
    from halo_harness.update import _quote_for_shell
    q = _quote_for_shell(lock)
    if _CONSTRAINT_RE.search(cmd):
        return _CONSTRAINT_RE.sub(lambda m: m.group(1) + q, cmd, count=1)
    if cmd.lstrip().startswith("uv ") and " --reinstall" in cmd:
        return cmd.replace(" --reinstall", f" --reinstall --constraints {q}", 1)
    return cmd


def _tool_part(cmd: str) -> Optional[str]:
    """The installer half of a checkout's `git ... && <installer>` command."""
    tail = cmd.rsplit(" && ", 1)[-1].strip() if " && " in cmd else ""
    return tail if tail and not tail.startswith("git ") else None


def previous_install(kind: dict, before: dict, current_cmd: Optional[str], lock: Optional[str], *,
                     direct_url=None) -> Optional[dict]:
    """{cmd, cwd}: the command that installs again exactly what is installed now, or None."""
    from halo_harness.update import _quote_for_shell
    k, spec = kind.get("kind"), str(kind.get("spec") or "")
    if not current_cmd:
        return None
    if k in ("uv_tool", "pipx", "pip"):
        prev = spec
        vcs = direct_url.get("vcs_info") if isinstance(direct_url, dict) else None
        if spec.startswith("git+") and isinstance(vcs, dict) and vcs.get("commit_id"):
            prev = f"{spec.split('@', 1)[0]}@{vcs['commit_id']}"
        elif spec.startswith("git+") and before.get("commit"):
            prev = f"{spec.split('@', 1)[0]}@{before['commit']}"
        cmd = current_cmd.replace(spec, prev) if spec and prev != spec else current_cmd
        return {"cmd": _swap_lock(cmd, lock), "cwd": None}
    if k in ("editable_checkout", "dir_checkout", "bare_checkout") and before.get("commit") and spec:
        where = _quote_for_shell(spec)
        back = (f"git -C {where} reset --keep {before['commit']}" if before.get("branch")
                else f"git -C {where} checkout --detach {before['commit']}")
        tool = _tool_part(current_cmd) if k != "bare_checkout" else None
        return {"cmd": back + (f" && {_swap_lock(tool, lock)}" if tool else ""), "cwd": spec}
    return None


def halo_argv() -> list:
    """How the updater asks the installed halo for its version: `halo` (the runner finds it on PATH itself)."""
    return ["halo"]


def build_plan(*, cmd: str, cwd: Optional[str], before: dict, expect: dict, restore: Optional[dict],
               state_dir=None, wait_pids=(), stop_pids=(), held=(), supervisor_stop_file: Optional[str] = None,
               restart_supervisor: bool = False, windows: Optional[bool] = None, stop_starts=None,
               stop_what=None, force: bool = False) -> dict:
    """`stop_starts` (jb10): pid -> the start time RECORDED for it (the ledger's, or the one read when the scan saw it
    as a Halo process); the runner ends a stop pid only when its live start time equals it. A pid without one is not
    ended by number. 3.6.0.1 (jf-update): `stop_what` (pid -> the name the person knows it by, "Studio") and `force`
    (the run was `--force`) are only for what the updater says when it refuses."""
    from halo_harness import update_install as UI
    from halo_harness.update import format_version_line
    windows = os.name == "nt" if windows is None else windows
    rd = run_dir(state_dir)
    import secrets
    return {"version": 1, "log": str(_state(state_dir) / LOG_NAME), "result": str(rd / RESULT_NAME),
            "run_log": str(rd / RUN_LOG_NAME), "run_id": secrets.token_hex(8),
            "wait_pids": [int(p) for p in wait_pids], "stop_pids": [int(p) for p in stop_pids],
            "stop_starts": {str(int(p)): str(t) for p, t in (stop_starts or {}).items()
                            if t is not None and int(p) in {int(x) for x in stop_pids}}, "windows": bool(windows),
            "held": [{"pid": int(h["pid"]), "what": h.get("what") or "halo"} for h in held if h.get("pid")],
            "stop_what": {str(int(p)): str(w) for p, w in (stop_what or {}).items() if w}, "force": bool(force),
            "supervisor_stop_file": supervisor_stop_file, "restart_supervisor": bool(restart_supervisor),
            "install": {"cmd": cmd, "cwd": cwd}, "cert_env": dict(UI.SYSTEM_CERTS_ENV),
            "cert_by_hand": UI.by_hand(cmd) if UI.is_uv(cmd) else None,
            "halo": halo_argv(),
            "before": {"line": format_version_line(before), "version": before.get("version"),
                       "commit": before.get("commit")},
            "expect": expect, "restore": restore, "pause_s": WINDOWS_PAUSE_S if windows else 0}


def _inside(path: str, prefix: str) -> bool:
    norm = lambda x: os.path.normcase(os.path.abspath(x)).rstrip("\\/")  # noqa: E731
    return norm(path).startswith(norm(prefix) + os.sep)


def outside_python() -> Optional[list]:
    """argv that runs a Python which is not the environment `halo update` replaces: the venv's base interpreter,
    else a python on PATH that is not under it (never the Store's alias stub), else `uv run`. None when none is.
    The running interpreter (or a venv's base) is never skipped for living under WindowsApps: a Microsoft Store
    Python lives there and it is running right now; only a name found on PATH there can be the stub."""
    in_venv = sys.prefix != getattr(sys, "base_prefix", sys.prefix)
    running = getattr(sys, "_base_executable", None) if in_venv else sys.executable
    on_path = [shutil.which(n) for n in ("python3", "python", "py")]
    for c in [running] + on_path:
        if not c or not os.path.isfile(c) or (c is not running and "windowsapps" in c.lower()):
            continue
        if in_venv and _inside(c, sys.prefix):
            continue
        return [c, "-I"] if os.path.basename(c).lower() not in ("py", "py.exe") else [c, "-3", "-I"]
    uv = shutil.which("uv")
    return [uv, "run", "--no-project", "--no-config", "python", "-I"] if uv else None


def write_runner(state_dir=None) -> Path:
    """update_runner.py's text, copied outside the environment it replaces."""
    src = Path(__file__).with_name(RUNNER_NAME).read_text(encoding="utf-8")
    path = run_dir(state_dir) / RUNNER_NAME
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(src, encoding="utf-8")
    return path


def write_plan(plan: dict, state_dir=None) -> Path:
    path = run_dir(state_dir) / PLAN_NAME
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(plan, indent=2), encoding="utf-8")
    return path


def launch_refusal(python: Optional[list] = None, *, need_python: bool = True) -> Optional[str]:
    """Why the updater cannot start here, as the one line to print, or None. `halo update` asks this BEFORE it stops
    any of the user's processes (judge should-fix 1). The switch is `HALO_NO_UPDATER=1`, or a scratch test home
    (`BRIDGE_TEST_HOME`); `BRIDGE_STATE_DIR` is a user's own setting and never blocks an update."""
    if os.environ.get("HALO_NO_UPDATER") == "1" or "BRIDGE_TEST_HOME" in os.environ:
        return ("halo update: the updater is switched off here (HALO_NO_UPDATER, or a test home), so nothing was "
                "installed")
    if need_python and not (python if python is not None else outside_python()):
        return ("halo update: no Python outside halo's own environment was found to run the updater, so nothing "
                "was installed; run the install from a shell instead")
    return None


def launch(plan: dict, *, state_dir=None, windows: Optional[bool] = None, python: Optional[list] = None,
           popen=None, execv=None, quiet: bool = False) -> Optional[int]:
    """Start the updater. POSIX: this process becomes it (exec; nothing of this environment runs after the
    install). Windows: the updater runs with NO console (closing a window or a Ctrl+C never stops it halfway) and
    waits for this halo to exit; its window is `update_runner.py --watch`, which shows its output and the outcome.
    Returns 0; None when it could not start (nothing was installed; the line was printed)."""
    from halo_harness import subprocess_safe as subprocess
    windows = os.name == "nt" if windows is None else windows
    if popen is None and execv is None:
        why = launch_refusal(python)
        if why:
            print(why, file=sys.stderr)
            return None
    py = python if python is not None else outside_python()
    if not py:
        print("halo update: no Python outside halo's own environment was found to run the updater, so nothing was "
              f"installed; run this from a shell instead: {(plan.get('install') or {}).get('cmd')}", file=sys.stderr)
        return None
    runner, plan_path = write_runner(state_dir), write_plan(plan, state_dir)
    argv = [*py, str(runner), str(plan_path)]
    if not windows:
        sys.stdout.flush()
        sys.stderr.flush()
        try:
            (execv or os.execv)(argv[0], argv)
        except OSError as e:
            print(f"halo update: the updater did not start ({e}); nothing was installed", file=sys.stderr)
            return None
        return 0  # an exec that returned: only a test's fake
    run = popen or subprocess.Popen
    from halo_harness import closing  # the updater and its window outlive this halo: kept, never in its Job
    detached = getattr(subprocess, "DETACHED_PROCESS", 0x08) | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0x200)
    started = None
    # One start path: kept_kwargs asks to leave Halo's Job, and subprocess_safe.Popen itself falls back (an outer Job
    # that forbids leaving: start_outside_job, else inside it with a line saying so). A retry here would repeat it.
    try:
        started = run(argv, **closing.kept_kwargs({
            "creationflags": detached, "stdin": subprocess.DEVNULL, "stdout": subprocess.DEVNULL,
            "stderr": subprocess.DEVNULL, "cwd": str(run_dir(state_dir)), "close_fds": True}))
    except OSError:
        started = None
    if started is None:
        print(f"halo update: the updater did not start ({runner}); nothing was installed; run `halo update` again",
              file=sys.stderr)
        return None
    closing.register_kept(started, "update", argv)
    window = getattr(subprocess, "CREATE_NEW_CONSOLE", 0x10) | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0x200)
    try:  # the window is a viewer only: without it the update still runs, its log says how it went
        run([*py, str(runner), "--watch", str(plan_path), str(getattr(started, "pid", "") or "")],
            **closing.kept_kwargs({"creationflags": window, "stdin": subprocess.DEVNULL,
                                   "cwd": str(run_dir(state_dir)), "close_fds": True}))
    except OSError:
        pass
    if not quiet:
        print("halo update: the install runs once this halo has exited (Windows cannot replace the files of a "
              "running halo), in its own window; it checks the new version and puts the old one back if it fails. "
              f"Its log: {plan.get('log')}; then `halo --version`")
    return 0


def last_result(state_dir=None) -> Optional[dict]:
    try:
        data = json.loads((run_dir(state_dir) / RESULT_NAME).read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else None
    except (OSError, ValueError):
        return None


def take_unseen_line(state_dir=None) -> Optional[str]:
    """The last updater's line once: it is marked seen when read."""
    got = last_result(state_dir)
    if not got or got.get("seen") or not got.get("line"):
        return None
    got["seen"] = True
    try:
        (run_dir(state_dir) / RESULT_NAME).write_text(json.dumps(got, indent=2), encoding="utf-8")
    except OSError:
        pass
    return str(got["line"])
