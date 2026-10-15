"""tests.helpers.cdp -- a small Chrome DevTools Protocol client on the
standard library (a websocket over a plain socket), for the Studio UI tests
that click and type in a real headless Chrome (Halo 3.0.4.0 round R6b):
launch, open a URL, evaluate JavaScript, click at a point or on an element,
press a key, drag, wait for a condition. Trusted input events, so a click is
the same pointerdown / focus / click sequence a person makes."""
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

KEYS = {"?": ("Slash", 191, 8), "Escape": ("Escape", 27, 0), "o": ("KeyO", 79, 0), "r": ("KeyR", 82, 0), "a": ("KeyA", 65, 0),
        # 3.0.5.0 R3: the Fleet hop keys
        "j": ("KeyJ", 74, 0), "k": ("KeyK", 75, 0), "f": ("KeyF", 70, 0), "p": ("KeyP", 80, 0), " ": ("Space", 32, 0),
        "Enter": ("Enter", 13, 0)}


class Chrome:
    def __init__(self, exe: str, width: int = 1500, height: int = 900):
        self.profile = tempfile.mkdtemp(prefix="halo-cdp-")
        self.proc = subprocess.Popen([exe, "--headless=new", "--disable-gpu", "--hide-scrollbars", "--no-first-run",
                                      "--no-default-browser-check", f"--user-data-dir={self.profile}", "--remote-debugging-port=0",
                                      f"--window-size={width},{height}", "about:blank"],
                                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        self.buf = b""
        self.seq = 0
        self.down = False
        try:
            port = self._port()
            opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
            targets = json.loads(opener.open(f"http://127.0.0.1:{port}/json/list", timeout=10).read())
            page = next(t for t in targets if t.get("type") == "page")
            self._connect(page["webSocketDebuggerUrl"])
        except Exception:
            self.close()
            raise

    def _port(self) -> int:
        path = os.path.join(self.profile, "DevToolsActivePort")
        deadline = time.time() + 30
        while time.time() < deadline:
            try:
                with open(path, encoding="utf-8") as f:
                    return int(f.read().split()[0])
            except (OSError, ValueError, IndexError):
                time.sleep(0.1)
        raise RuntimeError("Chrome did not open its DevTools port")

    # -- the websocket -------------------------------------------------------------
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
            raise RuntimeError(f"DevTools refused the websocket: {head[:80]!r}")

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
            payload = self._read(n)
            op = b1 & 0x0F
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

    # -- what a test does ------------------------------------------------------------
    def go(self, url: str) -> None:
        self.call("Page.navigate", url=url)

    def js(self, expr: str):
        r = self.call("Runtime.evaluate", expression=expr, returnByValue=True, awaitPromise=True)
        if r.get("exceptionDetails"):
            raise RuntimeError(f"{expr[:80]}: {r['exceptionDetails'].get('exception', {}).get('description', r['exceptionDetails'])}")
        return r.get("result", {}).get("value")

    def wait(self, expr: str, timeout: float = 20):
        deadline = time.time() + timeout
        while True:
            try:
                got = self.js(expr)
            except RuntimeError:
                got = None
            if got:
                return got
            if time.time() > deadline:
                raise TimeoutError(f"waited {timeout}s for: {expr}")
            time.sleep(0.1)

    def rect(self, expr: str) -> list:
        """The viewport rect [x, y, w, h] of the element `expr` evaluates to."""
        return self.js(f"(() => {{ const r = ({expr}).getBoundingClientRect(); return [r.left, r.top, r.width, r.height]; }})()")

    def mouse(self, kind: str, x: float, y: float) -> None:
        """One mouse event; a move between press and release carries the held left button (a drag)."""
        if kind == "mousePressed":
            self.down = True
        held = self.down and kind != "mouseReleased"
        self.call("Input.dispatchMouseEvent", type=kind, x=x, y=y, button="left" if kind != "mouseMoved" or held else "none",
                  buttons=1 if held else 0, clickCount=1)
        if kind == "mouseReleased":
            self.down = False

    def click(self, x: float, y: float) -> None:
        for kind in ("mouseMoved", "mousePressed", "mouseReleased"):
            self.mouse(kind, x, y)

    def click_on(self, expr: str, fx: float = 0.5, fy: float = 0.5) -> None:
        x, y, w, h = self.rect(expr)
        self.click(x + w * fx, y + h * fy)

    def drag(self, x0: float, y0: float, x1: float, y1: float, steps: int = 8) -> None:
        self.mouse("mouseMoved", x0, y0)
        self.mouse("mousePressed", x0, y0)
        for i in range(1, steps + 1):
            self.mouse("mouseMoved", x0 + (x1 - x0) * i / steps, y0 + (y1 - y0) * i / steps)
        self.mouse("mouseReleased", x1, y1)

    def key(self, key: str) -> None:
        code, vk, mods = KEYS[key]
        text = key if len(key) == 1 else ""
        self.call("Input.dispatchKeyEvent", type="keyDown", key=key, code=code, text=text, windowsVirtualKeyCode=vk, modifiers=mods)
        self.call("Input.dispatchKeyEvent", type="keyUp", key=key, code=code, windowsVirtualKeyCode=vk, modifiers=mods)

    def type_text(self, text: str) -> None:
        """Text into the focused field, as typing it would put it there."""
        self.call("Input.insertText", text=text)

    def shot(self, path, width: int = 1500, height: int = 900, scale: float = 2) -> int:
        """A PNG of the page at `width` x `height` CSS px and `scale` device pixels per px; returns its size."""
        self.call("Emulation.setDeviceMetricsOverride", width=width, height=height, deviceScaleFactor=scale, mobile=False)
        data = base64.b64decode(self.call("Page.captureScreenshot", format="png", captureBeyondViewport=False)["data"])
        with open(path, "wb") as f:
            f.write(data)
        return len(data)

    def close(self) -> None:
        try:  # a clean exit closes the page's connections (no reset on the server's side)
            self.go("about:blank")
            self.call("Browser.close")
        except Exception:
            pass
        try:
            self.sock.close()
        except Exception:
            pass
        try:
            self.proc.wait(timeout=10)
        except Exception:
            self.proc.terminate()
            try:
                self.proc.wait(timeout=10)
            except Exception:
                pass
        shutil.rmtree(self.profile, ignore_errors=True)
