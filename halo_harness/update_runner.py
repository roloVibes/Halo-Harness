"""halo_harness.update_runner -- the standalone updater `halo update` and `/update` hand the install to (Halo 3.6.0.0
R13). The owner's Windows `halo update` once died inside the tool environment it was replacing and left it without the
package; so the reinstall never runs from inside that environment any more.

This file is a SCRIPT as much as a module: it imports nothing from halo_harness (standard library only), because the
running halo copies its text to `<state>/run/update_runner.py`, outside the environment it replaces, and starts it with
a Python that is not that environment's (update_plan.outside_python: the base interpreter of the venv, a python on
PATH, or `uv run`), with one argument, the plan file `<state>/run/update-plan.json` (update_plan.build_plan):

1. wait for the old halo (`wait_pids`: its pid and the `halo.exe` launcher above it) to be gone; a halo that does not
   exit within `wait_s` installs nothing;
2. stop what the plan names (`stop_pids`, the supervisor's stop file first);
3. Windows: other halo processes that hold the install's files (`held`, from a `--force`) are waited for, and when
   they still run nothing installs (a held file is the usual way a Windows reinstall breaks halfway);
4. run the install (`install.cmd`; one retry on the system's certificate store when uv names a certificate);
5. VERIFY: `halo --version` answers the expected version (or commit);
6. when the install or the verification failed: put back what was there (`restore.cmd`: the previous install's exact
   spec and a lock of its packages) and verify that, then say in ONE plain line what happened and the one command to
   run by hand;
7. start the supervisor again when it ran, print the new version's summary.

Judge pass (3.6.0.0 R13): the installer runs in its own process group and its output is streamed as it comes; while
the install, the check and the putting back run, Ctrl+C / SIGHUP / console events are ignored and any way out of the
install (BaseException) still runs the putting back; the result file and the log's last line are always written;
waits and stops check the pid AND its start time; a pid that is both to stop and to wait for is stopped first. On
Windows the updater runs with no console and `--watch` is its window (it stays open on any outcome but `updated`).

Every line goes to stdout and to `<state>/update.log`; the outcome to `<state>/run/update-result.json`
({outcome: updated | restored | unchanged | broken | not_started, line, ...}), which the next `halo update` reports.

    run_plan(plan, run_fn=, alive_fn=, kill_fn=, sleep_fn=, clock=, out=) -> (exit code, result)   the seam tests use
    main(argv)                                                                                   the script's entry
"""
from __future__ import annotations

import json
import os
import re
import shutil
import signal
import subprocess
import sys
import time

WAIT_S = 300.0
HELD_WAIT_S = 60.0
INSTALL_TIMEOUT_S = 1800.0
VERSION_TIMEOUT_S = 60.0
_CERT_RE = re.compile(r"invalid peer certificate|UnknownIssuer|CERTIFICATE_VERIFY_FAILED|certificate verify failed"
                      r"|self[- ]signed certificate|unable to get local issuer certificate", re.IGNORECASE)
MORE = "halo whatsnew for the rest"


def _alive(pid: int) -> bool:
    """Whether a process with this pid still runs (no signal is sent, nothing is ended)."""
    if pid <= 0:
        return False
    if os.name == "nt":
        import ctypes
        from ctypes import wintypes
        k32 = ctypes.WinDLL("kernel32", use_last_error=True)
        k32.OpenProcess.restype = wintypes.HANDLE
        handle = k32.OpenProcess(0x1000, False, int(pid))  # PROCESS_QUERY_LIMITED_INFORMATION
        if not handle:
            return ctypes.get_last_error() == 5  # access denied: it exists
        try:
            code = wintypes.DWORD()
            ok = k32.GetExitCodeProcess(handle, ctypes.byref(code))
            return bool(ok) and code.value == 259  # STILL_ACTIVE
        finally:
            k32.CloseHandle(handle)
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError:
        return False
    try:  # Linux: a process that has exited but was not reaped yet (a zombie) is gone for the updater
        with open(f"/proc/{int(pid)}/stat", encoding="utf-8", errors="replace") as fh:
            return fh.read().rsplit(")", 1)[-1].split()[0] != "Z"
    except (OSError, IndexError):
        return True


def _kill(pid: int) -> None:
    """Ends one process the plan named by pid (never by name)."""
    if os.name == "nt":
        tk = shutil.which("taskkill") or os.path.join(os.environ.get("SystemRoot", r"C:\Windows"), "System32",
                                                       "taskkill.exe")
        subprocess.run([tk, "/PID", str(pid), "/T", "/F"], capture_output=True, text=True, timeout=30)
        return
    for sig in (signal.SIGTERM, getattr(signal, "SIGKILL", signal.SIGTERM)):
        try:
            os.kill(pid, sig)
        except OSError:
            return
        deadline = time.monotonic() + 2.0
        while time.monotonic() < deadline and _alive(pid):
            time.sleep(0.1)
        if not _alive(pid):
            return


def _start_time(pid: int):
    """When the process with this pid started (an opaque value compared for equality), or None when unknown: a pid
    the OS gave to another program since it was listed is never waited on or ended (judge item 10)."""
    if pid <= 0:
        return None
    if os.name == "nt":
        try:
            import ctypes
            from ctypes import wintypes
            k32 = ctypes.WinDLL("kernel32", use_last_error=True)
            k32.OpenProcess.restype = wintypes.HANDLE
            handle = k32.OpenProcess(0x1000, False, int(pid))
            if not handle:
                return None
            try:
                c, e, k, u = (wintypes.FILETIME() for _ in range(4))
                if not k32.GetProcessTimes(handle, ctypes.byref(c), ctypes.byref(e), ctypes.byref(k), ctypes.byref(u)):
                    return None
                return str((c.dwHighDateTime << 32) | c.dwLowDateTime)
            finally:
                k32.CloseHandle(handle)
        except Exception:  # noqa: BLE001
            return None
    # jb10: the same text Halo's ledger records (bg_run.process_start_time), so a plan's recorded start time is
    # compared like for like: /proc's field 22, or where there is no /proc (macOS; HALO_TEST_NO_PROC=1 in tests)
    # "ps:" + `lstart` read in UTC with the C locale, its fields joined by one space.
    if os.environ.get("HALO_TEST_NO_PROC") != "1" and os.path.exists("/proc/self/stat"):
        try:
            with open(f"/proc/{int(pid)}/stat", encoding="utf-8", errors="replace") as fh:
                return fh.read().rsplit(")", 1)[-1].split()[19]
        except (OSError, IndexError):
            return None
    ps = shutil.which("ps")
    if not ps:
        return None
    try:
        r = subprocess.run([ps, "-o", "lstart=", "-p", str(int(pid))], capture_output=True, text=True, timeout=5,
                           env={**os.environ, "LC_ALL": "C", "LANG": "C", "TZ": "UTC0"})
        parts = (r.stdout or "").split()
        return "ps:" + " ".join(parts[-5:]) if r.returncode == 0 and len(parts) >= 5 else None
    except (OSError, subprocess.SubprocessError):
        return None


def last_line(text: str) -> str:
    lines = [ln.strip() for ln in (text or "").splitlines() if ln.strip()]
    return lines[-1] if lines else ""


def answers(line: str, want: dict) -> bool:
    """`halo --version`'s last line is `halo <version> (<commit>, <ref>)`: does it answer what `want` names
    (version: that exact version; commit: that commit; not_commit: anything but that one)?"""
    if not line.startswith("halo "):
        return False
    version, commit, not_commit = want.get("version"), want.get("commit"), want.get("not_commit")
    if version and not re.search(r"(?<![\w.])halo " + re.escape(str(version)) + r"(?![\w.])", line):
        return False
    if commit and str(commit)[:7] not in line:
        return False
    if not_commit and str(not_commit)[:7] in line:
        return False
    return True


def _own_group_kw() -> dict:
    """The installer runs in its own process group / session (a Ctrl+C at the terminal never reaches it) and, on
    Windows, without a console window of its own."""
    if os.name == "nt":
        return {"creationflags": getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0x200)
                | getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)}
    return {"start_new_session": True}


def stream_run(cmd, *, out, shell: bool = True, cwd=None, env=None, timeout: float = INSTALL_TIMEOUT_S):
    """Runs `cmd` in its own process group and says each line of its output AS IT COMES (a silent two minutes
    invites a Ctrl+C); returns (code, all the text). A timeout ends it (its group) and answers 124."""
    import threading
    proc = subprocess.Popen(cmd, shell=shell, cwd=cwd or None, env=env, stdin=subprocess.DEVNULL,
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, errors="replace",
                            **_own_group_kw())
    lines: list = []

    def pump():
        for raw in proc.stdout:
            line = raw.rstrip("\r\n")
            lines.append(line)
            out(line)
    t = threading.Thread(target=pump, daemon=True)
    t.start()
    try:
        code = proc.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        _end_tree(proc.pid)
        code = 124
        out(f"halo update: the command ran past {timeout:.0f} s and was ended")
    t.join(5.0)
    return code, "\n".join(lines)


def _end_tree(pid: int) -> None:
    if os.name == "nt":
        tk = shutil.which("taskkill") or os.path.join(os.environ.get("SystemRoot", r"C:\Windows"), "System32",
                                                       "taskkill.exe")
        subprocess.run([tk, "/PID", str(pid), "/T", "/F"], capture_output=True, text=True, timeout=30)
        return
    try:
        os.killpg(pid, signal.SIGKILL)
    except OSError:
        pass


class _Run:
    def __init__(self, plan: dict, run_fn, alive_fn, kill_fn, sleep_fn, clock, out, start_fn, stream):
        self.plan, self.run_fn, self.alive_fn, self.kill_fn = plan, run_fn, alive_fn, kill_fn
        self.sleep_fn, self.clock, self.out, self.start_fn, self.stream = sleep_fn, clock, out, start_fn, stream
        self.halo = list(plan.get("halo") or ["halo"])
        self.started: dict = {}  # pid -> its start time when the updater first saw it

    def say(self, line: str) -> None:
        self.out(line)

    def note(self, pids) -> None:
        for p in pids:
            if p not in self.started:
                self.started[p] = self.start_fn(p)

    def same(self, pid: int) -> bool:
        """The pid still runs AND is the process the updater first saw (a reused pid is not)."""
        if not self.alive_fn(pid):
            return False
        then = self.started.get(pid)
        return then is None or self.start_fn(pid) in (None, then)

    def wait_gone(self, pids, limit: float) -> list:
        self.note(pids)
        deadline = self.clock() + limit
        left = [p for p in pids if self.same(p)]
        while left and self.clock() < deadline:
            self.sleep_fn(1.0)
            left = [p for p in left if self.same(p)]
        return left

    def proven(self, pid: int) -> bool:
        """The pid runs AND its start time, known when first seen, is read again now and equals it. Unknown on either
        side is no proof (jb10): a signal is never sent on a pid number alone."""
        then = self.started.get(pid)
        return then is not None and self.alive_fn(pid) and self.start_fn(pid) == then

    def stop(self, pid: int) -> bool:
        """True when the pid was left running unproven (Windows counts it as a Halo that may hold the files)."""
        if not self.same(pid):
            self.say(f"halo update: pid {pid} is gone (or is another program now): not stopped")
            return False
        if not self.proven(pid):
            self.say(f"halo update: pid {pid} was not stopped: its start time was not recorded or cannot be read, so "
                     f"it cannot be proven to be the Halo process listed; `halo ps` names Halo's own, end it by hand "
                     f"if it is one")
            return True
        self.say(f"halo update: stopping pid {pid}")
        try:
            self.kill_fn(int(pid))
        except Exception as e:  # noqa: BLE001 -- one that will not stop is named by the held check
            self.say(f"halo update: pid {pid} did not stop ({e})")
        return False

    def shell(self, cmd: str, cwd, env_extra=None) -> "tuple[int, str]":
        env = {**os.environ, **env_extra} if env_extra else None
        timeout = float(self.plan.get("install_timeout_s") or INSTALL_TIMEOUT_S)
        if self.stream:
            try:
                return stream_run(cmd, out=self.say, cwd=cwd, env=env, timeout=timeout)
            except (OSError, subprocess.SubprocessError) as e:
                self.say(f"halo update: the command did not run: {e}")
                return 1, str(e)
        kw = {"env": env} if env else {}
        try:
            r = self.run_fn(cmd, shell=True, cwd=cwd or None, capture_output=True, text=True, timeout=timeout, **kw)
        except (OSError, subprocess.SubprocessError) as e:
            self.say(f"halo update: the command did not run: {e}")
            return 1, str(e)
        text = "\n".join(t for t in ((r.stdout or "").rstrip(), (getattr(r, "stderr", "") or "").rstrip()) if t)
        if text:
            self.say(text)
        return int(r.returncode or 0), text

    def install(self, cmd: str, cwd) -> int:
        code, text = self.shell(cmd, cwd)
        cert_env = self.plan.get("cert_env")
        if code != 0 and cert_env and cmd.lstrip().startswith("uv ") and _CERT_RE.search(text or ""):
            self.say("halo update: the installer did not trust a certificate on this network (a proxy or TLS "
                     "inspection between this box and GitHub or PyPI); trying once more with the system's "
                     "certificate store")
            if self.plan.get("cert_by_hand"):
                self.say(f"halo update: running: {self.plan['cert_by_hand']}")
            code, _text = self.shell(cmd, cwd, cert_env)
            if code != 0:
                self.say("halo update: still refused. Check `env | grep -i proxy` on this box (an intercepting proxy "
                         "needs its CA in the system store), then run the command above by hand")
        return code

    def run(self, argv, timeout: float):
        kw = {"creationflags": getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)} if (
            os.name == "nt" and self.stream) else {}
        return self.run_fn(argv, capture_output=True, text=True, timeout=timeout, **kw)

    def version(self) -> str:
        try:
            r = self.run([*self.halo, "--version"], VERSION_TIMEOUT_S)
        except (OSError, subprocess.SubprocessError):
            return ""
        return last_line(r.stdout) if int(r.returncode or 0) == 0 else ""

    def restart_supervisor(self) -> None:
        if not self.plan.get("restart_supervisor"):
            return
        try:
            self.run([*self.halo, "supervise", "--daemon"], 60)
            self.say("halo update: started the supervisor again")
        except (OSError, subprocess.SubprocessError) as e:
            self.say(f"halo update: the supervisor did not start again ({e}); `halo supervise --daemon` starts it")

    def whats_new(self) -> None:
        """The new version's summary and any installed pack older than the one it ships (the new halo says both)."""
        try:
            got = self.run([*self.halo, "whatsnew", "--summary"], 30)
            text = (got.stdout or "").strip() if int(got.returncode or 0) == 0 else ""
        except (OSError, subprocess.SubprocessError):
            text = ""
        if text:
            self.say(f"halo update: what is new -- {text}")
        self.say(f"halo update: {MORE}")
        try:
            got = self.run([*self.halo, "pack", "list", "--json"], 60)
            rows = (json.loads(got.stdout or "{}").get("packs") or []) if int(got.returncode or 0) == 0 else []
        except (OSError, subprocess.SubprocessError, ValueError, AttributeError):
            rows = []
        for r in rows if isinstance(rows, list) else []:
            if isinstance(r, dict) and r.get("ships") and r.get("id"):
                self.say(f"halo update: {r['id']} {r.get('version') or '?'} is older than the {r['ships']} this "
                         f"Halo ships: halo pack update {r['id']}")


def _result(outcome: str, line: str, **extra) -> dict:
    return {"outcome": outcome, "line": line, "at": time.time(), "seen": False, **extra}


class _Shield:
    """While the install, the check and the putting back run, a Ctrl+C, a closed terminal (SIGHUP) or, on Windows,
    a console event does not end the updater: the roll-back always gets to run (judge item 2)."""

    def __init__(self, on: bool):
        self.on, self.saved = on, {}

    def __enter__(self):
        if not self.on:
            return self
        for name in ("SIGINT", "SIGHUP", "SIGBREAK", "SIGTERM"):
            sig = getattr(signal, name, None)
            if sig is None:
                continue
            try:
                self.saved[sig] = signal.signal(sig, signal.SIG_IGN)
            except (ValueError, OSError):  # not the main thread, or not settable here
                pass
        if os.name == "nt":
            try:
                import ctypes
                ctypes.windll.kernel32.SetConsoleCtrlHandler(None, True)  # this process ignores Ctrl+C
            except Exception:  # noqa: BLE001
                pass
        return self

    def __exit__(self, *exc):
        for sig, old in self.saved.items():
            try:
                signal.signal(sig, old)
            except (ValueError, OSError):
                pass
        if self.on and os.name == "nt":
            try:
                import ctypes
                ctypes.windll.kernel32.SetConsoleCtrlHandler(None, False)
            except Exception:  # noqa: BLE001
                pass
        return False


def run_plan(plan: dict, *, run_fn=None, alive_fn=None, kill_fn=None, sleep_fn=None, clock=None,
             out=None, start_fn=None, protect: bool = False) -> "tuple[int, dict]":
    """The whole update from the plan; (0, result) when the new version answers, else (1, result). Whatever ends
    the install or its check -- an error, a Ctrl+C, a closed window -- the putting back still runs."""
    real = alive_fn is None
    r = _Run(plan, run_fn or subprocess.run, alive_fn or _alive, kill_fn or _kill, sleep_fn or time.sleep,
             clock or time.monotonic, out or print, start_fn or (_start_time if real else (lambda p: None)),
             stream=run_fn is None)
    before = plan.get("before") or {}
    before_line = before.get("line") or "the installed halo"
    expect = plan.get("expect") or {}
    target = expect.get("label") or "the newest"
    install = plan.get("install") or {}
    cmd = install.get("cmd") or ""
    wait_pids = [int(p) for p in plan.get("wait_pids") or []]
    stop_pids = [int(p) for p in plan.get("stop_pids") or []]
    # jb10: a stop pid's identity is the start time the PLAN recorded for it (the ledger's), never one read here: a
    # pid with none (an old plan, a row with no start time) is not ended by number
    starts = plan.get("stop_starts") if isinstance(plan.get("stop_starts"), dict) else {}
    for pid in stop_pids:
        r.started[pid] = starts.get(str(pid)) or None
    r.note(wait_pids)  # who they are now: a pid reused later is neither waited on nor ended
    r.say(f"halo update: installed {before_line}")
    both = [p for p in stop_pids if p in wait_pids]
    unproven = []
    for pid in both:  # one that must be stopped is stopped first, never waited on for minutes (judge item 3)
        if r.stop(pid):
            unproven.append(pid)
    left = r.wait_gone(wait_pids, float(plan.get("wait_s") or WAIT_S))
    if left:
        line = (f"halo update: halo (pid {', '.join(map(str, left))}) did not exit, so nothing was installed and "
                f"{before_line} is unchanged; close it and run `halo update` again")
        r.say(line)
        return 1, _result("not_started", line, before=before_line)
    if plan.get("supervisor_stop_file"):
        try:
            with open(plan["supervisor_stop_file"], "w", encoding="utf-8") as fh:
                fh.write("stop\n")
            r.sleep_fn(5.0)
        except OSError:
            pass
    for pid in stop_pids:
        if pid not in both and r.stop(pid):
            unproven.append(pid)
    held = [h for h in plan.get("held") or [] if isinstance(h, dict) and h.get("pid")]
    if plan.get("windows", os.name == "nt"):  # jb10: files are never replaced under a Halo that may still run
        held += [{"pid": p, "what": "halo"} for p in unproven if all(int(h["pid"]) != p for h in held)]
    if held:
        still = set(r.wait_gone([int(h["pid"]) for h in held], float(plan.get("held_wait_s") or HELD_WAIT_S)))
        named = [f"{h.get('what') or 'halo'} (pid {h['pid']})" for h in held if int(h["pid"]) in still]
        if named:
            line = (f"halo update: not installing -- these halo processes still run and hold the install's files: "
                    f"{', '.join(named)}; {before_line} is unchanged. Close them (or run `halo update` without "
                    f"--force, which stops them) and try again")
            r.say(line)
            return 1, _result("not_started", line, before=before_line)
    with _Shield(protect):
        return _install_and_check(r, plan, before, before_line, expect, target, cmd, install)


def _install_and_check(r, plan, before, before_line, expect, target, cmd, install) -> "tuple[int, dict]":
    r.say(f"halo update: running: {cmd}  (its output follows as it comes; a minute or two)")
    stopped_by = None
    code, got = 1, ""
    try:
        code = r.install(cmd, install.get("cwd"))
        got = r.version()
    except BaseException as e:  # noqa: BLE001 -- Ctrl+C, a closed window, anything: the roll-back still runs
        stopped_by = e
    if stopped_by is None and code == 0 and answers(got, expect):
        r.say(f"halo update: before {before_line}")
        r.say(f"halo update: after  {got}")
        r.restart_supervisor()
        if before.get("version") and not answers(got, {"version": before.get("version")}):
            r.whats_new()
        line = f"halo update: done -- {before_line} -> {got}"
        return 0, _result("updated", line, before=before_line, after=got)
    if stopped_by is not None:
        what = "Ctrl+C" if isinstance(stopped_by, KeyboardInterrupt) else type(stopped_by).__name__
        reason = f"the install was interrupted ({what})"
    elif code != 0:
        reason = f"the installer exited with code {code}"
    elif got:
        reason = f"`halo --version` answered {got!r}, not {target}"
    else:
        reason = "`halo --version` did not answer after the install"
    r.say(f"halo update: the update to {target} failed: {reason}")
    restore = plan.get("restore") or {}
    want_before = {"version": before.get("version"), "commit": before.get("commit")}
    restore_code = None
    now = ""
    try:
        if restore.get("cmd"):
            r.say(f"halo update: putting back {before_line}: {restore['cmd']}")
            restore_code, _t = r.shell(restore["cmd"], restore.get("cwd"))
        now = r.version()
    except BaseException as e:  # noqa: BLE001
        r.say(f"halo update: putting it back was interrupted ({type(e).__name__})")
    again = cmd or "halo update"
    if answers(now, want_before):
        r.restart_supervisor()
        if restore.get("cmd") and restore_code == 0:
            line = (f"halo update: the update to {target} failed ({reason}); {before_line} was put back and answers "
                    f"again. To try the update by hand: {again}")
            outcome = "restored"
        else:  # nothing was put back (none to run, or it failed): what answers is what was never touched
            line = (f"halo update: the update to {target} failed ({reason}); nothing changed, {before_line} still "
                    f"answers. To try again by hand: {again}")
            outcome = "unchanged"
        r.say(line)
        return 1, _result(outcome, line, before=before_line, after=now)
    by_hand = restore.get("cmd") or cmd
    line = (f"halo update: the update to {target} failed ({reason}) and halo does not answer now"
            + (" (putting it back failed too)" if restore.get("cmd") else "")
            + f"; run this by hand: {by_hand}")
    r.say(line)
    return 1, _result("broken", line, before=before_line, after=now, by_hand=by_hand)


def _write_result(result_path, result: dict) -> None:
    if not result_path:
        return
    try:
        tmp = result_path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(result, fh, indent=2)
        os.replace(tmp, result_path)
    except OSError:
        pass


def watch(plan_path: str, runner_pid: "int | None" = None, *, poll: float = 0.5) -> int:
    """Windows: the updater's window. The updater itself runs with no console (closing this window or a Ctrl+C here
    never stops it); this shows its output as it comes, then the outcome, and stays open on any outcome but
    `updated`, saying where the log is (judge item 11)."""
    with open(plan_path, encoding="utf-8") as fh:
        plan = json.load(fh)
    run_log, result_path, run_id = plan.get("run_log"), plan.get("result"), plan.get("run_id")
    print("Halo update -- this window shows the updater's progress; closing it does not stop the update.", flush=True)
    pos, result = 0, None
    while result is None:
        try:
            with open(run_log, encoding="utf-8", errors="replace") as fh:
                fh.seek(pos)
                chunk = fh.read()
                pos = fh.tell()
            if chunk:
                print(chunk, end="", flush=True)
        except (OSError, TypeError):
            pass
        try:
            with open(result_path, encoding="utf-8") as fh:
                got = json.load(fh)
            if got.get("run_id") == run_id:
                result = got
                break
        except (OSError, ValueError, TypeError):
            pass
        if runner_pid and not _alive(runner_pid):
            time.sleep(poll)
            try:
                with open(result_path, encoding="utf-8") as fh:
                    got = json.load(fh)
                result = got if got.get("run_id") == run_id else None
            except (OSError, ValueError, TypeError):
                result = None
            if result is None:
                result = {"outcome": "broken", "line": "halo update: the updater stopped without saying how it ended"}
            break
        time.sleep(poll)
    print("", flush=True)
    print(result.get("line") or "", flush=True)
    if result.get("outcome") == "updated":
        time.sleep(float(plan.get("pause_s") or 5))
        return 0
    print(f"The log: {plan.get('log')}. Press Enter to close this window.", flush=True)
    try:
        input()
    except (EOFError, KeyboardInterrupt, OSError):
        time.sleep(600)
    return 1


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if os.name == "nt":
        os.environ.setdefault("NoDefaultCurrentDirectoryInExePath", "1")
    if argv[:1] == ["--watch"] and len(argv) >= 2:
        return watch(argv[1], int(argv[2]) if len(argv) > 2 and argv[2].isdigit() else None)
    if not argv:
        print("usage: update_runner.py <plan.json> | --watch <plan.json> [pid]", file=sys.stderr)
        return 2
    with open(argv[0], encoding="utf-8") as fh:
        plan = json.load(fh)
    if list(plan.get("halo") or ["halo"]) == ["halo"]:  # the installed halo, found on PATH the way the shell finds it
        plan["halo"] = [shutil.which("halo") or "halo"]
    log_path, result_path = plan.get("log"), plan.get("result")
    logs = []
    for path, mode in ((log_path, "a"), (plan.get("run_log"), "w")):
        if path:
            try:
                os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
                fh = open(path, mode, encoding="utf-8")
                fh.write(f"=== halo update {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
                fh.flush()
                logs.append(fh)
            except OSError:
                pass

    def out(line: str) -> None:
        try:
            print(line, flush=True)
        except (OSError, ValueError, AttributeError):
            pass
        for fh in logs:
            try:
                fh.write(line + "\n")
                fh.flush()
            except OSError:
                pass

    code, result = 1, None
    try:
        code, result = run_plan(plan, out=out, protect=True)
    except BaseException as e:  # noqa: BLE001 -- whatever the way out, the outcome is written and said
        by_hand = (plan.get("restore") or {}).get("cmd") or (plan.get("install") or {}).get("cmd") or "halo update"
        what = "Ctrl+C" if isinstance(e, KeyboardInterrupt) else f"{type(e).__name__}: {e}"
        line = f"halo update: the updater stopped ({what}); if `halo --version` fails, run: {by_hand}"
        out(line)
        code, result = 1, _result("broken", line, by_hand=by_hand)
    finally:
        if result is None:
            result = _result("broken", "halo update: the updater stopped without an outcome")
        result["run_id"] = plan.get("run_id")
        _write_result(result_path, result)
        for fh in logs:
            try:
                fh.write(f"=== {result.get('outcome')}\n")
                fh.close()
            except OSError:
                pass
    return code


if __name__ == "__main__":
    sys.exit(main())
