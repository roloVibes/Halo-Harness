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


class _Run:
    def __init__(self, plan: dict, run_fn, alive_fn, kill_fn, sleep_fn, clock, out):
        self.plan, self.run_fn, self.alive_fn, self.kill_fn = plan, run_fn, alive_fn, kill_fn
        self.sleep_fn, self.clock, self.out = sleep_fn, clock, out
        self.halo = list(plan.get("halo") or ["halo"])

    def say(self, line: str) -> None:
        self.out(line)

    def wait_gone(self, pids, limit: float) -> list:
        deadline = self.clock() + limit
        left = [p for p in pids if self.alive_fn(p)]
        while left and self.clock() < deadline:
            self.sleep_fn(1.0)
            left = [p for p in left if self.alive_fn(p)]
        return left

    def shell(self, cmd: str, cwd, env_extra=None) -> "tuple[int, str]":
        kw = {"env": {**os.environ, **env_extra}} if env_extra else {}
        try:
            r = self.run_fn(cmd, shell=True, cwd=cwd or None, capture_output=True, text=True,
                            timeout=float(self.plan.get("install_timeout_s") or INSTALL_TIMEOUT_S), **kw)
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

    def version(self) -> str:
        try:
            r = self.run_fn([*self.halo, "--version"], capture_output=True, text=True, timeout=VERSION_TIMEOUT_S)
        except (OSError, subprocess.SubprocessError):
            return ""
        return last_line(r.stdout) if int(r.returncode or 0) == 0 else ""

    def restart_supervisor(self) -> None:
        if not self.plan.get("restart_supervisor"):
            return
        try:
            self.run_fn([*self.halo, "supervise", "--daemon"], capture_output=True, text=True, timeout=60)
            self.say("halo update: started the supervisor again")
        except (OSError, subprocess.SubprocessError) as e:
            self.say(f"halo update: the supervisor did not start again ({e}); `halo supervise --daemon` starts it")

    def whats_new(self) -> None:
        """The new version's summary and any installed pack older than the one it ships (the new halo says both)."""
        try:
            got = self.run_fn([*self.halo, "whatsnew", "--summary"], capture_output=True, text=True, timeout=30)
            text = (got.stdout or "").strip() if int(got.returncode or 0) == 0 else ""
        except (OSError, subprocess.SubprocessError):
            text = ""
        if text:
            self.say(f"halo update: what is new -- {text}")
        self.say(f"halo update: {MORE}")
        try:
            got = self.run_fn([*self.halo, "pack", "list", "--json"], capture_output=True, text=True, timeout=60)
            rows = (json.loads(got.stdout or "{}").get("packs") or []) if int(got.returncode or 0) == 0 else []
        except (OSError, subprocess.SubprocessError, ValueError, AttributeError):
            rows = []
        for r in rows if isinstance(rows, list) else []:
            if isinstance(r, dict) and r.get("ships") and r.get("id"):
                self.say(f"halo update: {r['id']} {r.get('version') or '?'} is older than the {r['ships']} this "
                         f"Halo ships: halo pack update {r['id']}")


def _result(outcome: str, line: str, **extra) -> dict:
    return {"outcome": outcome, "line": line, "at": time.time(), "seen": False, **extra}


def run_plan(plan: dict, *, run_fn=None, alive_fn=None, kill_fn=None, sleep_fn=None, clock=None,
             out=None) -> "tuple[int, dict]":
    """The whole update from the plan; (0, result) when the new version answers, else (1, result)."""
    r = _Run(plan, run_fn or subprocess.run, alive_fn or _alive, kill_fn or _kill, sleep_fn or time.sleep,
             clock or time.monotonic, out or print)
    before = plan.get("before") or {}
    before_line = before.get("line") or "the installed halo"
    expect = plan.get("expect") or {}
    target = expect.get("label") or "the newest"
    install = plan.get("install") or {}
    cmd = install.get("cmd") or ""
    r.say(f"halo update: installed {before_line}")
    left = r.wait_gone([int(p) for p in plan.get("wait_pids") or []], float(plan.get("wait_s") or WAIT_S))
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
    for pid in plan.get("stop_pids") or []:
        r.say(f"halo update: stopping pid {pid}")
        try:
            r.kill_fn(int(pid))
        except Exception as e:  # noqa: BLE001 -- one that will not stop is named by the held check below
            r.say(f"halo update: pid {pid} did not stop ({e})")
    held = [h for h in plan.get("held") or [] if isinstance(h, dict) and h.get("pid")]
    if held:
        still = set(r.wait_gone([int(h["pid"]) for h in held], float(plan.get("held_wait_s") or HELD_WAIT_S)))
        named = [f"{h.get('what') or 'halo'} (pid {h['pid']})" for h in held if int(h["pid"]) in still]
        if named:
            line = (f"halo update: not installing -- these halo processes still run and hold the install's files: "
                    f"{', '.join(named)}; {before_line} is unchanged. Close them (or run `halo update` without "
                    f"--force, which stops them) and try again")
            r.say(line)
            return 1, _result("not_started", line, before=before_line)
    r.say(f"halo update: running: {cmd}  (the installer's output prints when it ends; a minute or two)")
    code = r.install(cmd, install.get("cwd"))
    got = r.version()
    if code == 0 and answers(got, expect):
        r.say(f"halo update: before {before_line}")
        r.say(f"halo update: after  {got}")
        r.restart_supervisor()
        if before.get("version") and not answers(got, {"version": before.get("version")}):
            r.whats_new()
        line = f"halo update: done -- {before_line} -> {got}"
        return 0, _result("updated", line, before=before_line, after=got)
    if code != 0:
        reason = f"the installer exited with code {code}"
    elif got:
        reason = f"`halo --version` answered {got!r}, not {target}"
    else:
        reason = "`halo --version` did not answer after the install"
    r.say(f"halo update: the update to {target} failed: {reason}")
    restore = plan.get("restore") or {}
    want_before = {"version": before.get("version"), "commit": before.get("commit")}
    if restore.get("cmd"):
        r.say(f"halo update: putting back {before_line}: {restore['cmd']}")
        r.shell(restore["cmd"], restore.get("cwd"))
    now = r.version()
    if answers(now, want_before):
        r.restart_supervisor()
        again = cmd or "halo update"
        if restore.get("cmd"):
            line = (f"halo update: the update to {target} failed ({reason}); {before_line} was put back and answers "
                    f"again. To try the update by hand: {again}")
            outcome = "restored"
        else:
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


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if os.name == "nt":
        os.environ.setdefault("NoDefaultCurrentDirectoryInExePath", "1")
    if not argv:
        print("usage: update_runner.py <plan.json>", file=sys.stderr)
        return 2
    with open(argv[0], encoding="utf-8") as fh:
        plan = json.load(fh)
    if list(plan.get("halo") or ["halo"]) == ["halo"]:  # the installed halo, found on PATH the way the shell finds it
        plan["halo"] = [shutil.which("halo") or "halo"]
    log_path, result_path = plan.get("log"), plan.get("result")
    log = None
    if log_path:
        try:
            os.makedirs(os.path.dirname(log_path) or ".", exist_ok=True)
            log = open(log_path, "a", encoding="utf-8")
            log.write(f"=== halo update {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
        except OSError:
            log = None

    def out(line: str) -> None:
        try:
            print(line, flush=True)
        except (OSError, ValueError):
            pass
        if log is not None:
            try:
                log.write(line + "\n")
                log.flush()
            except OSError:
                pass

    try:
        code, result = run_plan(plan, out=out)
    except Exception as e:  # noqa: BLE001 -- the updater says what stopped it instead of a traceback
        by_hand = (plan.get("restore") or {}).get("cmd") or (plan.get("install") or {}).get("cmd") or "halo update"
        line = f"halo update: the updater stopped ({type(e).__name__}: {e}); if `halo --version` fails, run: {by_hand}"
        out(line)
        code, result = 1, _result("broken", line, by_hand=by_hand)
    if result_path:
        try:
            tmp = result_path + ".tmp"
            with open(tmp, "w", encoding="utf-8") as fh:
                json.dump(result, fh, indent=2)
            os.replace(tmp, result_path)
        except OSError:
            pass
    if log is not None:
        log.write(f"=== {result.get('outcome')}\n")
        log.close()
    if plan.get("pause_s"):  # Windows: the updater's own window stays a moment so its last line can be read
        time.sleep(float(plan["pause_s"]))
    return code


if __name__ == "__main__":
    sys.exit(main())
