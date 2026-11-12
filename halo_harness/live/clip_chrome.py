"""halo_harness.live.clip_chrome -- the one headless Chrome a replay clip is filmed in (Halo 3.4.1.0 R1 "Time"):
launch, the DevTools websocket, evaluate, wait for a value, a PNG of a region, close. The suite's drivers have their
own client (tests/helpers/cdp.py, with the suite's Chrome lock); this is the package's, for `halo replay clip` and
Studio's Export a clip. Stdlib only.

3.4.1.2 (SERVERS-5 / PACKS-8): on Linux and macOS the DevTools protocol runs over two pipes
(`--remote-debugging-pipe`: Chrome reads fd 3 and writes fd 4, given to it by `os.posix_spawn`), so no port is open
for another process on the machine to attach to. Windows has no fd 3 / fd 4 to hand a child from Python (Chrome reads
them there through the C runtime's inherited-handle block, which `subprocess` cannot fill), so there Chrome keeps
`--remote-debugging-port=0` on loopback, and what it films is a throwaway Studio of its own (live/replay_clip.py
`_studio`: its own token, the replay page's GETs only, stopped after): the live Studio's token never enters it.
"""

from __future__ import annotations

import base64
import json
import os
import shutil
import socket
import struct
import subprocess
import tempfile
import time
import urllib.request
from pathlib import Path
from typing import Optional

CANDIDATES = ("C:/Program Files/Google/Chrome/Application/chrome.exe",
              "C:/Program Files (x86)/Google/Chrome/Application/chrome.exe",
              "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome")
NAMES = ("google-chrome", "google-chrome-stable", "chromium", "chromium-browser", "chrome")


def find_chrome() -> Optional[str]:
    """`HALO_CHROME`, then the usual install paths, then PATH; None when there is none."""
    env = os.environ.get("HALO_CHROME", "")
    if env and Path(env).exists():
        return env
    for cand in CANDIDATES:
        if Path(cand).exists():
            return cand
    return next((shutil.which(n) for n in NAMES if shutil.which(n)), None)


def pipe_ok() -> bool:
    """Whether DevTools can run over pipes here (POSIX with os.posix_spawn), not a port (Windows)."""
    return os.name == "posix" and hasattr(os, "posix_spawn")


class Chrome:
    def __init__(self, exe: str, width: int, height: int, *, pipe: "bool | None" = None):
        self.profile = tempfile.mkdtemp(prefix="halo-clip-")
        self.buf, self.seq, self.sock, self.pipe, self.session = b"", 0, None, None, ""
        root = getattr(os, "geteuid", lambda: -1)() == 0
        use_pipe = pipe_ok() if pipe is None else pipe
        self.argv = ([exe, "--headless=new", "--disable-gpu", "--hide-scrollbars", "--no-first-run",
                      "--no-default-browser-check", f"--user-data-dir={self.profile}",
                      "--remote-debugging-pipe" if use_pipe else "--remote-debugging-port=0",
                      f"--window-size={width},{height}", "about:blank"] + (["--no-sandbox"] if root else []))
        try:
            if use_pipe:
                from halo_harness.live.clip_pipe import spawn
                self.proc, self.pipe = spawn(self.argv)
                target = self._first_page()
                self.session = self.call("Target.attachToTarget", targetId=target["targetId"], flatten=True)["sessionId"]
            else:
                self.proc = subprocess.Popen(self.argv, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                port = self._port()
                opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
                targets = json.loads(opener.open(f"http://127.0.0.1:{port}/json/list", timeout=10).read())
                self._connect(next(t for t in targets if t.get("type") == "page")["webSocketDebuggerUrl"])
            self.call("Emulation.setDeviceMetricsOverride", width=width, height=height, deviceScaleFactor=1, mobile=False)
        except Exception:
            self.close()
            raise

    def _first_page(self) -> dict:
        deadline = time.time() + 30
        while True:
            pages = [t for t in self.call("Target.getTargets")["targetInfos"] if t.get("type") == "page"]
            if pages:
                return pages[0]
            if time.time() > deadline:
                return {"targetId": self.call("Target.createTarget", url="about:blank")["targetId"]}
            time.sleep(0.1)

    def _port(self) -> int:
        path, deadline = os.path.join(self.profile, "DevToolsActivePort"), time.time() + 60
        while time.time() < deadline:
            try:
                with open(path, encoding="utf-8") as f:
                    return int(f.read().split()[0])
            except (OSError, ValueError, IndexError):
                time.sleep(0.1)
        raise RuntimeError("Chrome did not open its DevTools port")

    def _connect(self, url: str) -> None:
        hostport, path = url.split("://", 1)[1].split("/", 1)
        host, port = hostport.rsplit(":", 1)
        self.sock = socket.create_connection((host, int(port)), timeout=60)
        key = base64.b64encode(os.urandom(16)).decode("ascii")
        self.sock.sendall((f"GET /{path} HTTP/1.1\r\nHost: {hostport}\r\nUpgrade: websocket\r\nConnection: Upgrade\r\n"
                           f"Sec-WebSocket-Key: {key}\r\nSec-WebSocket-Version: 13\r\n\r\n").encode("ascii"))
        while b"\r\n\r\n" not in self.buf:
            chunk = self.sock.recv(4096)
            if not chunk:
                raise RuntimeError("DevTools closed during the handshake")
            self.buf += chunk
        head, self.buf = self.buf.split(b"\r\n\r\n", 1)
        if b" 101 " not in head.split(b"\r\n", 1)[0]:
            raise RuntimeError("DevTools refused the websocket")

    def _send(self, text: str) -> None:
        data = text.encode("utf-8")
        n = len(data)
        head = bytes([0x81]) + (bytes([0x80 | n]) if n < 126 else bytes([0x80 | 126]) + struct.pack(">H", n) if n < 65536
                                 else bytes([0x80 | 127]) + struct.pack(">Q", n))
        mask = os.urandom(4)
        self.sock.sendall(head + mask + bytes(b ^ mask[i % 4] for i, b in enumerate(data)))

    def _read(self, n: int) -> bytes:
        while len(self.buf) < n:
            chunk = self.sock.recv(1 << 16)
            if not chunk:
                raise RuntimeError("DevTools closed the connection")
            self.buf += chunk
        out, self.buf = self.buf[:n], self.buf[n:]
        return out

    def _recv(self) -> str:
        msg = b""
        while True:
            b1, b2 = self._read(2)
            n = b2 & 0x7F
            if n == 126:
                n = struct.unpack(">H", self._read(2))[0]
            elif n == 127:
                n = struct.unpack(">Q", self._read(8))[0]
            if b2 & 0x80:
                self._read(4)
            payload, op = self._read(n), b1 & 0x0F
            if op == 8:
                raise RuntimeError("DevTools closed the websocket")
            if op in (9, 10):
                continue
            msg += payload
            if b1 & 0x80:
                return msg.decode("utf-8")

    def call(self, method: str, **params):
        self.seq += 1
        mid = self.seq
        msg = {"id": mid, "method": method, "params": params}
        if self.pipe is not None and self.session and not method.startswith(("Target.", "Browser.")):
            msg["sessionId"] = self.session  # the page's session over the browser's one pipe
        (self.pipe.send if self.pipe is not None else self._send)(json.dumps(msg))
        while True:
            m = json.loads(self.pipe.recv() if self.pipe is not None else self._recv())
            if m.get("id") == mid:
                if "error" in m:
                    raise RuntimeError(f"{method}: {m['error']}")
                return m.get("result", {})

    def js(self, expr: str):
        r = self.call("Runtime.evaluate", expression=expr, returnByValue=True, awaitPromise=True)
        if r.get("exceptionDetails"):
            raise RuntimeError(f"{expr[:80]}: {r['exceptionDetails']}")
        return r.get("result", {}).get("value")

    def wait(self, expr: str, timeout: float = 30):
        deadline = time.time() + timeout
        while True:
            try:
                got = self.js(expr)
            except RuntimeError:
                got = None
            if got:
                return got
            if time.time() > deadline:
                raise TimeoutError(f"waited {timeout}s for: {expr[:120]}")
            time.sleep(0.05)

    def png(self, x: float, y: float, w: float, h: float, scale: float) -> bytes:
        clip = {"x": x, "y": y, "width": w, "height": h, "scale": scale}
        return base64.b64decode(self.call("Page.captureScreenshot", format="png", clip=clip)["data"])

    def close(self) -> None:
        try:
            if self.sock is not None or self.pipe is not None:
                try:
                    self.call("Browser.close")
                except Exception:
                    pass
            if self.sock is not None:
                self.sock.close()
            if self.pipe is not None:
                self.pipe.close()
        except Exception:
            pass
        if getattr(self, "proc", None) is not None:
            try:
                self.proc.wait(timeout=10)
            except Exception:
                self.proc.kill()
        shutil.rmtree(self.profile, ignore_errors=True)
