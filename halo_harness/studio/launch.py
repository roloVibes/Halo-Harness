"""halo_harness.studio.launch -- start Halo Studio as its own process, find
the one that is already running, stop it (Halo 3.0.2.0).

`halo studio` writes `~/.halo/studio.json` ({pid, port, token}, private)
while it serves. `existing_url` turns that into the page URL when the port
still answers, so a second `halo studio`, the wizard's "Open Studio"
buttons and `/roles` from a plain shell all land on the same instance
instead of starting another. `launch_detached` spawns `halo studio` with
no console of its own, waits for the URL it prints, and returns it; the
spawned Studio joins `~/.halo/run/children.json` (children.py), so the session
that started it ends it on quit (3.2.2.0 R3; 3.4.1.1: a shell's has no owner).
"""

from __future__ import annotations

from halo_harness.selfexec import python_argv  # 3.6.0.0 R10: never the working folder's copy
import json
import os
import socket
from halo_harness import subprocess_safe as subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Optional

from halo_harness.studio.server import STUDIO_MODES, studio_info_path


def read_info(state_dir: Path) -> Optional[dict]:
    try:
        data = json.loads(studio_info_path(Path(state_dir)).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if not isinstance(data, dict):
        return None
    # A hand-edited or half-written file ("port": "abc") reads as no Studio,
    # never as an exception out of the wizard's worker (review 3 item 76).
    try:
        port = int(data.get("port"))
    except (TypeError, ValueError):
        return None
    return dict(data, port=port) if 0 < port < 65536 else None


def port_answers(port: int, timeout: float = 0.3) -> bool:
    try:
        with socket.create_connection(("127.0.0.1", int(port)), timeout=timeout):
            return True
    except (OSError, ValueError, TypeError, OverflowError):
        return False


def _query(mode: Optional[str], edit: Optional[str]) -> str:
    """`?mode=<mode>`, or with an edit target (3.1.1.0 R3, studio/edit_target.py) `?mode=agents&view=crew&edit=agent:<name>`;
    for Session (3.1.4.0 R2, studio/session_open.py) `edit` is the session: `?mode=session&session=<sid>`."""
    if mode == "session" and edit:
        from halo_harness.studio.session_open import SectionTarget
        return SectionTarget.from_text(edit).query()  # 3.3.11.0 R1: `prompt:<sid>` adds &prompt=1
    if edit:
        from halo_harness.studio.edit_target import parse
        target, _why = parse(edit)
        if target is not None:
            return target.query()
    from halo_harness.studio.modes import known  # 3.3.13.0 R2: a pack's section (<pack id>--<section>) too
    return f"?mode={mode}" if known(mode) else ""


def url_from_info(info: dict, mode: Optional[str] = None, edit: Optional[str] = None) -> str:
    query = _query(mode, edit)
    token = info.get("token") or ""
    return f"http://127.0.0.1:{info['port']}/{query}" + (f"#t={token}" if token else "")


def existing_url(state_dir: Path, mode: Optional[str] = None, edit: Optional[str] = None) -> str:
    """The running instance's URL (with `mode`, or the edit target, in the query), or ''."""
    info = read_info(state_dir)
    if not info or not port_answers(info["port"]):
        return ""
    return url_from_info(info, mode, edit)


LAST_FAILURE: dict = {}  # 3.6.0.0 R10: why the last launch_detached gave no URL ("exit code 1: <last line>")


def owned_by_me(info: Optional[dict]) -> bool:
    """3.6.0.0 R10: this process started the Studio studio.json names (its ledger entry, or the owner it records)."""
    if not info or not isinstance(info.get("pid"), int):
        return False
    from halo_harness import children, closing
    pid, start = closing.me()
    if info.get("owner_pid") == pid and (not info.get("owner_start") or not start or info["owner_start"] == start):
        return True
    return any(e.get("pid") == info["pid"] and e.get("what") == "studio" and closing._mine(e) for e in children.load())


def own_url(state_dir: Path, mode: Optional[str] = None, edit: Optional[str] = None) -> str:
    """The running Studio's URL only when this process started it ('' otherwise): a launch never attaches to a
    server it did not start (3.6.0.0 R10, closing.py)."""
    info = read_info(state_dir)
    if not owned_by_me(info) or not port_answers(info["port"]):
        return ""
    return url_from_info(info, mode, edit)


def live_owned(state_dir: Path) -> Optional[dict]:
    """3.6.0.0 R10 (judge item 3): studio.json's Studio when it answers and its owner is ALIVE -- another terminal's
    session, or a `halo studio` a person runs (its own owner). A launch may use it (never adopt it: it stays with its
    owner). None for no Studio, one that does not answer, or one whose owner is gone (a leftover: the sweep's)."""
    info = read_info(Path(state_dir))
    if not info or not port_answers(info["port"]):
        return None
    from halo_harness import children
    if not children.same_process(info.get("pid"), info.get("pstart")):
        return None
    owner = info.get("owner_pid")
    if owner is None:  # a Studio from before 3.6.0.0 R10 records no owner: one a person started, not a leftover
        return info
    return info if children.same_process(owner, info.get("owner_start")) else None


def whose(info: dict) -> str:
    """"your own `halo studio` (pid 4242)" / "the halo of pid 4100 (pid 4242)": who a Studio belongs to, in words."""
    pid, owner = info.get("pid"), info.get("owner_pid")
    if owner is None or owner == pid:
        return f"a `halo studio` started on its own (pid {pid})"
    return f"the halo of pid {owner} (Studio pid {pid})"


def failure_line() -> str:
    """Why the last start gave no URL, for "Studio did not start: <why>" ('' when nothing is known)."""
    return str(LAST_FAILURE.get("why") or "")


START_S = 45.0  # 3.6.0.0 fx: on the macOS CI runner a fresh Studio printed its address after ~35 s


def _stop_unstarted(proc, state_dir: Path) -> None:
    """3.6.0.0 fx: a Studio that gave no address in time is stopped (it and its ledger row), not left starting behind
    the terminal setup that runs instead."""
    from halo_harness import children, children_stop
    try:
        entry = next((e for e in children.load(state_dir) if e.get("pid") == proc.pid), None)
        if entry is not None:
            children_stop.stop_entry(entry, state_dir=state_dir, timeout=2.0)
        elif proc.poll() is None:
            children_stop.terminate(proc.pid, timeout=2.0, recorded=children.start_time(proc.pid))
        proc.wait(timeout=5)
    except Exception:
        pass


def _ledger_names_the_studio(proc, argv: list, state_dir: Path) -> None:
    """3.6.0.0 fx: an installed Halo's python can be a launcher (the Windows venv's python.exe) that runs the real
    interpreter as its child, so Popen's pid is not the Studio's. The ledger row takes the pid studio.json names (the
    launcher's stays as `launcher_pid`), so a close asks Studio's own shutdown route and `halo ps` shows one row.
    A test's stand-in for Popen never joins the ledger (children.spawned)."""
    from halo_harness import children
    if not children.spawned(proc):
        return
    info: Optional[dict] = None
    for _ in range(10):  # the URL may come from stdout a moment before studio.json lands
        info = read_info(Path(state_dir))
        if info:
            break
        time.sleep(0.1)
    pid = (info or {}).get("pid")
    if not isinstance(pid, int) or pid == proc.pid or not owned_by_me(info):
        return
    if children.register(pid, "studio", argv, state_dir=state_dir, launcher_pid=proc.pid,
                          start=info.get("pstart")) is not None:
        children.unregister(proc.pid, state_dir=state_dir)


def launch_detached(mode: Optional[str], *, cwd: Path, state_dir: Path, open_browser: bool = True,
                    timeout: float = START_S, edit: Optional[str] = None) -> str:
    """Reuse the Studio THIS process started, else spawn `halo studio --mode <mode>` (or `--edit <target>`, 3.1.1.0
    R3) and return the URL it prints ('' on failure; `failure_line()` says why). 3.6.0.0 R10: the Studio belongs to
    this process -- it is in the ledger with this process as its owner, it watches this process and ends within two
    seconds of it (closing.py), and it opens no browser itself (this process does: a browser started from inside
    the Studio would be the Studio's child)."""
    LAST_FAILURE.clear()
    url = own_url(state_dir, mode, edit)
    if url:
        if open_browser:
            _open(url)
        return url
    from halo_harness.selfexec import python_argv
    argv = [*python_argv(unbuffered=True), "studio", "--cwd", str(cwd)]
    if mode == "session":  # 3.1.4.0 R2: `edit` is the session to watch ('' = the newest live one); 3.3.11.0 R1: --prompt
        from halo_harness.studio.session_open import SectionTarget
        t = SectionTarget.from_text(edit or "")
        argv += ["--session"] + ([t.session] if t.session else []) + (["--prompt"] if t.prompt else [])
    elif edit:
        argv += ["--edit", edit]
    elif mode in STUDIO_MODES or mode == "glance" or "--" in str(mode or ""):  # 3.3.13.0 R2: a pack's section; 3.4.1.0 R4: the glance
        argv += ["--mode", mode]
    argv.append("--no-open")
    from halo_harness import closing
    env = {**os.environ, **closing.owner_env()}
    kwargs: dict = {"stdin": subprocess.DEVNULL, "stdout": subprocess.PIPE, "stderr": subprocess.STDOUT, "text": True,
                    "encoding": "utf-8", "errors": "replace", "env": env}
    if sys.platform == "win32":
        kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP | getattr(subprocess, "CREATE_NO_WINDOW", 0)
    else:
        kwargs["start_new_session"] = True
    try:
        proc = subprocess.Popen(argv, **kwargs)
    except OSError as e:
        LAST_FAILURE["why"] = f"{type(e).__name__}: {e}"
        return ""
    from halo_harness import children
    if children.spawned(proc):  # 3.6.0.0 R10: always this process's (children.spawned takes the safe Popen too)
        children.register(proc.pid, "studio", argv, state_dir=state_dir)
    found: dict = {}
    tail: list = []

    def _read() -> None:
        try:
            for line in proc.stdout:  # type: ignore[union-attr]
                if line.strip():
                    tail[:] = (tail + [line.rstrip()])[-5:]
                if "url" not in found and "Halo Studio is at " in line:
                    found["url"] = line.split("Halo Studio is at ", 1)[1].strip()
        except Exception:
            pass

    threading.Thread(target=_read, daemon=True).start()  # reads to the end: the pipe never fills
    deadline = time.time() + timeout
    url = ""
    while time.time() < deadline:  # studio.json appears as soon as the server binds; stdout is the fallback
        url = found.get("url") or own_url(state_dir, mode, edit)
        if url:
            break
        if proc.poll() is not None:
            time.sleep(0.2)  # the reader takes the last lines
            last = tail[-1] if tail else "no output"
            LAST_FAILURE["why"] = f"it exited with code {proc.returncode}: {last}"
            return ""
        time.sleep(0.2)
    url = url or found.get("url", "")
    if not url:
        LAST_FAILURE["why"] = f"it gave no address within {int(timeout)} s" + (f" (last line: {tail[-1]})" if tail else "")
        _stop_unstarted(proc, state_dir)
        return ""
    _ledger_names_the_studio(proc, argv, state_dir)
    if open_browser:
        _open(url)
    return url


HOLD_LINE = "Studio runs while this command does: Ctrl+C here stops it."


def hold(state_dir: Path, say=print, poll_s: float = 0.5) -> bool:
    """3.6.0.0 R10: a shell command that started a Studio (`halo setup team`, `halo studio --edit ...`) stays in the
    foreground while it serves -- there is no detached Studio. Returns at once (False) when the Studio studio.json
    names is not this process's own (a running session's was focused, or a test's stand-in answered); else waits
    until Ctrl+C or the Studio stops, and True."""
    from halo_harness import children
    info = read_info(Path(state_dir))
    if not owned_by_me(info):
        return False
    say(HOLD_LINE)
    try:
        while children.same_process(info["pid"], info.get("pstart")):
            time.sleep(poll_s)
    except KeyboardInterrupt:
        pass
    return True


def api_call(state_dir: Path, method: str, path: str, body: Optional[dict] = None,
             timeout: float = 5.0) -> "Optional[tuple]":
    """3.0.5.0 R2: one call on the running Studio's loopback API with its stored token (`halo fleet`
    reads `GET /api/live` and sends commands through it): `(status, body)`, or None when none answers."""
    import http.client
    info = read_info(state_dir)
    if not info:
        return None
    conn = http.client.HTTPConnection("127.0.0.1", info["port"], timeout=timeout)
    try:
        from halo_harness.studio.owner_proof import cli_headers  # 3.4.1.2: the token and the owner proof (studio.json)
        conn.request(method, "/api/" + path.lstrip("/"), body=json.dumps(body).encode("utf-8") if body is not None else None, headers=cli_headers(info))
        resp = conn.getresponse()
        status, data = resp.status, resp.read()
    except (OSError, http.client.HTTPException):
        return None
    finally:
        conn.close()
    try:
        obj = json.loads(data.decode("utf-8") or "{}")
    except ValueError:
        obj = {}
    return status, obj if isinstance(obj, (dict, list)) else {}


def _clear_info(state_dir: Path) -> None:
    try:
        studio_info_path(Path(state_dir)).unlink()
    except OSError:
        pass


def _ask_shutdown(info: dict) -> bool:
    """POST /api/shutdown with the stored token: True when a Studio answered 200 and its port went quiet."""
    import urllib.request
    from halo_harness.studio.owner_proof import cli_headers  # 3.4.1.2: shutdown needs the owner proof (studio.json's salt)
    req = urllib.request.Request(f"http://127.0.0.1:{int(info['port'])}/api/shutdown", data=b"{}", method="POST", headers=cli_headers(info))
    try:
        with urllib.request.urlopen(req, timeout=3) as resp:
            if resp.status != 200:
                return False
    except (OSError, ValueError):
        return False
    deadline = time.time() + 5
    while port_answers(info["port"]) and time.time() < deadline:
        time.sleep(0.1)
    return not port_answers(info["port"])


def _windows_cmdline(pid: int) -> str:
    try:
        r = subprocess.run(["powershell", "-NoProfile", "-Command",  # UTF-8 both ways: see update.PS_UTF8
                            "[Console]::OutputEncoding = [System.Text.Encoding]::UTF8; "
                            f"(Get-CimInstance Win32_Process -Filter 'ProcessId={int(pid)}').CommandLine"],
                           capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=15)
    except (OSError, subprocess.SubprocessError, ValueError):
        return ""
    return (r.stdout or "").strip()


def pid_is_studio(pid: int, info: Optional[dict] = None) -> bool:
    """True only with proof this pid is the Studio: the start time studio.json
    recorded (`pstart`, 3.2.2.0) still matches, else /proc (Linux) or the
    process's command line (Windows) shows `halo studio`. No proof, no kill."""
    recorded = (info or {}).get("pstart")
    if recorded:
        from halo_harness.children import same_process
        return same_process(int(pid), str(recorded))
    try:
        argv = Path(f"/proc/{int(pid)}/cmdline").read_bytes().split(b"\0")
    except (OSError, ValueError):
        if sys.platform != "win32":
            return False
        from halo_harness.update import halo_what
        return halo_what(_windows_cmdline(pid)) == "studio"
    names = [os.path.basename(x) for x in argv[:3]]  # the interpreter, then `-m halo_harness` or the halo launcher
    return b"studio" in argv[1:] and (b"halo_harness" in b" ".join(argv[:6]) or any(n.startswith((b"halo", b"halo.")) for n in names))


_pid_is_studio = pid_is_studio


def stop(state_dir: Path) -> "tuple[bool, str]":
    info = read_info(state_dir)
    if not info or not info.get("pid"):
        return False, "no Studio is running (no studio.json)"
    pid = int(info["pid"])
    if port_answers(info["port"]) and _ask_shutdown(info):
        _clear_info(state_dir)
        from halo_harness.children import unregister
        unregister(pid, state_dir=state_dir)
        return True, f"stopped Studio (pid {pid}, port {info.get('port')})"
    from halo_harness.children import pid_running, unregister
    if not pid_running(pid):
        _clear_info(state_dir)
        unregister(pid, state_dir=state_dir)
        return False, f"pid {pid} is not running; cleared studio.json"
    if not pid_is_studio(pid, info):
        _clear_info(state_dir)
        return False, f"studio.json was stale (pid {pid} is not a Studio); cleared it"
    # The signal second (SIGTERM, then SIGKILL after 5 s; Windows: taskkill /PID, then /F), by pid only.
    from halo_harness.children_stop import terminate
    gone = terminate(pid, timeout=5.0, recorded=info.get("pstart"))
    _clear_info(state_dir)
    unregister(pid, state_dir=state_dir)
    if not gone:
        return False, f"Studio (pid {pid}) is still running after the stop"
    return True, f"stopped Studio (pid {pid}, port {info.get('port')})"


def _open(url: str) -> bool:
    """True when a browser took the URL."""
    from halo_harness.closing import open_url  # 3.6.0.0 R10: the browser is the person's, never Halo's child
    return open_url(url)
