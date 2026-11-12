"""halo_harness.live.clip_chrome -- the one headless Chrome a replay clip is filmed in (Halo 3.4.1.0 R1 "Time"):
launch, the DevTools websocket, evaluate, wait for a value, a PNG of a region, close. The suite's drivers have their
own client (tests/helpers/cdp.py, with the suite's Chrome lock); this is the package's, for `halo replay clip` and
Studio's Export a clip. Stdlib only.
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


class Chrome:
    def __init__(self, exe: str, width: int, height: int):
        self.profile = tempfile.mkdtemp(prefix="halo-clip-")
        self.buf, self.seq, self.sock = b"", 0, None
        root = getattr(os, "geteuid", lambda: -1)() == 0
        self.proc = subprocess.Popen([exe, "--headless=new", "--disable-gpu", "--hide-scrollbars", "--no-first-run",
                                      "--no-default-browser-check", f"--user-data-dir={self.profile}",
                                      "--remote-debugging-port=0", f"--window-size={width},{height}", "about:blank"]
                                     + (["--no-sandbox"] if root else []),
                                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        try:
            port = self._port()
            opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
            targets = json.loads(opener.open(f"http://127.0.0.1:{port}/json/list", timeout=10).read())
            self._connect(next(t for t in targets if t.get("type") == "page")["webSocketDebuggerUrl"])
            self.call("Emulation.setDeviceMetricsOverride", width=width, height=height, deviceScaleFactor=1, mobile=False)
        except Exception:
            self.close()
            raise

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
        self._send(json.dumps({"id": mid, "method": method, "params": params}))
        while True:
            m = json.loads(self._recv())
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
            if self.sock is not None:
                try:
                    self.call("Browser.close")
                except Exception:
                    pass
                self.sock.close()
        except Exception:
            pass
        if self.proc is not None:
            try:
                self.proc.wait(timeout=10)
            except Exception:
                self.proc.kill()
        shutil.rmtree(self.profile, ignore_errors=True)
