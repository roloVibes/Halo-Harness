"""halo_harness.remote.signal_link -- one live connection to signal-cli
(Halo 2.0.9 round 3): the argv of the spawned `jsonRpc` child, the `_Link`
file pair around it, and `open_link` for the three transports (stdio child,
`daemon --socket`, `daemon --tcp`). Used by signal_transport.py."""

from __future__ import annotations

import json
import os
import socket
import subprocess
import threading
import time
from typing import Callable

from halo_harness.remote.client import open_socket


class Link:
    """One live connection: file-likes for the child's stdout/stdin.
    `interrupt()` ends the peer end (safe from any thread, wakes a blocked
    reader); `close()` also releases the files (the reader thread calls it
    after its loop returns)."""

    def __init__(self, rfile, wfile, interrupter: Callable[[], None]) -> None:
        self.rfile, self.wfile, self._interrupt = rfile, wfile, interrupter
        self.wlock = threading.Lock()
        self.born = time.monotonic()

    def write(self, obj: dict) -> None:
        data = (json.dumps(obj, ensure_ascii=False) + "\n").encode("utf-8")
        with self.wlock:
            self.wfile.write(data)
            self.wfile.flush()

    def interrupt(self) -> None:
        try:
            self._interrupt()
        except Exception:
            pass

    def close(self) -> None:
        self.interrupt()
        for f in (self.wfile, self.rfile):
            try:
                f.close()
            except Exception:
                pass


def build_argv(cfg: dict) -> list:
    b = cfg.get("binary") or "signal-cli"
    argv = [str(x) for x in b] if isinstance(b, (list, tuple)) else [str(b)]
    if cfg.get("account"):
        argv += ["-a", str(cfg["account"])]
    argv += ["--trust-new-identities", "never", "--scrub-log", "-d", str(cfg["data_dir"])]
    argv += [str(x) for x in cfg.get("extra_args") or []]
    argv += ["jsonRpc", "--ignore-stories", "--ignore-avatars", "--ignore-stickers",
             "--receive-mode", str(cfg.get("receive_mode") or "manual")]
    return argv


def open_link(cfg: dict, popen=subprocess.Popen) -> Link:
    mode = cfg.get("transport") or "stdio"
    if mode == "stdio":
        flags = 0x08000000 if os.name == "nt" else 0
        proc = popen(build_argv(cfg), stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                     stderr=subprocess.DEVNULL, bufsize=0, creationflags=flags)

        def interrupter() -> None:
            try:
                proc.terminate()
                proc.wait(2.0)
            except Exception:
                try:
                    proc.kill()
                except Exception:
                    pass
        return Link(proc.stdout, proc.stdin, interrupter)
    if mode == "socket":
        endpoint = "unix:" + str(cfg.get("socket") or "")
    elif mode == "tcp":
        endpoint = "tcp:" + str(cfg.get("tcp") or "127.0.0.1:7583")
    else:
        raise OSError(f"unknown signal transport {mode!r}")
    sock = open_socket(endpoint, 10.0)  # the same loopback/Unix client the control socket uses
    sock.settimeout(None)
    return Link(sock.makefile("rb"), sock.makefile("wb"), lambda: sock.shutdown(socket.SHUT_RDWR))
