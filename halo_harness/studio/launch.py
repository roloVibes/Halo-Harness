"""halo_harness.studio.launch -- start Halo Studio as its own process, find
the one that is already running, stop it (Halo 3.0.2.0).

`halo studio` writes `~/.halo/studio.json` ({pid, port, token}, private)
while it serves. `existing_url` turns that into the page URL when the port
still answers, so a second `halo studio`, the wizard's "Open Studio"
buttons and `/roles` from a plain shell all land on the same instance
instead of starting another. `launch_detached` spawns `halo studio` with
no console of its own, waits for the URL it prints, and returns it; the
process outlives whoever launched it until `halo studio --stop`.
"""

from __future__ import annotations

import json
import os
import signal
import socket
import subprocess
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
    return data if isinstance(data, dict) and data.get("port") else None


def port_answers(port: int, timeout: float = 0.3) -> bool:
    try:
        with socket.create_connection(("127.0.0.1", int(port)), timeout=timeout):
            return True
    except OSError:
        return False


def url_from_info(info: dict, mode: Optional[str] = None) -> str:
    query = f"?mode={mode}" if mode in STUDIO_MODES else ""
    token = info.get("token") or ""
    return f"http://127.0.0.1:{info['port']}/{query}" + (f"#t={token}" if token else "")


def existing_url(state_dir: Path, mode: Optional[str] = None) -> str:
    """The running instance's URL (with `mode` in the query), or ''."""
    info = read_info(state_dir)
    if not info or not port_answers(info["port"]):
        return ""
    return url_from_info(info, mode)


def launch_detached(mode: Optional[str], *, cwd: Path, state_dir: Path, open_browser: bool = True,
                    timeout: float = 15.0) -> str:
    """Reuse the running Studio, else spawn `halo studio --mode <mode>` as
    a detached process and return the URL it prints ('' on timeout)."""
    url = existing_url(state_dir, mode)
    if url:
        if open_browser:
            _open(url)
        return url
    argv = [sys.executable, "-u", "-m", "halo_harness", "studio", "--cwd", str(cwd)]
    if mode in STUDIO_MODES:
        argv += ["--mode", mode]
    if not open_browser:
        argv.append("--no-open")
    kwargs: dict = {"stdin": subprocess.DEVNULL, "stdout": subprocess.PIPE, "stderr": subprocess.DEVNULL, "text": True,
                    "encoding": "utf-8", "errors": "replace"}
    if sys.platform == "win32":
        kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP | getattr(subprocess, "CREATE_NO_WINDOW", 0)
    else:
        kwargs["start_new_session"] = True
    try:
        proc = subprocess.Popen(argv, **kwargs)
    except OSError:
        return ""
    found: dict = {}

    def _read() -> None:
        try:
            for line in proc.stdout:  # type: ignore[union-attr]
                if "Halo Studio is at " in line:
                    found["url"] = line.split("Halo Studio is at ", 1)[1].strip()
                    break
        except Exception:
            pass

    threading.Thread(target=_read, daemon=True).start()
    deadline = time.time() + timeout
    while time.time() < deadline:  # studio.json appears as soon as the server binds; stdout is the fallback
        url = found.get("url") or existing_url(state_dir, mode)
        if url:
            threading.Thread(target=lambda: proc.stdout and proc.stdout.read(), daemon=True).start()  # keep the pipe drained
            return url
        if proc.poll() is not None:
            return ""
        time.sleep(0.2)
    return found.get("url", "")


def stop(state_dir: Path) -> "tuple[bool, str]":
    info = read_info(state_dir)
    if not info or not info.get("pid"):
        return False, "no Studio is running (no studio.json)"
    pid = int(info["pid"])
    try:
        os.kill(pid, signal.SIGTERM)
    except (OSError, ValueError) as e:
        try:
            studio_info_path(Path(state_dir)).unlink()
        except OSError:
            pass
        return False, f"pid {pid} is not running ({e}); cleared studio.json"
    try:
        studio_info_path(Path(state_dir)).unlink()
    except OSError:
        pass
    return True, f"stopped Studio (pid {pid}, port {info.get('port')})"


def _open(url: str) -> None:
    try:
        import webbrowser
        webbrowser.open(url)
    except Exception:
        pass
