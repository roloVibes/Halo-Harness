"""scripts/realcheck/steps_browser.py -- 3.6.0.6 W (the owner: "WE NEED THE HARNESS TO RUN AND CONTROL BROWSERS",
"FULLY CONTROL A BROWSER AND SEE IT"): Halo's built-in Browser tool for real, on this system's own installed browser.

`browser`: a real `halo -p` in a scratch home (browser.profile clean, so its folder must go too), the fake provider
scripted to call Browser open on a page this step serves on 127.0.0.1, click its button, take a screenshot, close
(fakes.py RC-BROWSER). It requires: the reply carries the page's text AFTER the click; a PNG in the session's
attachments folder; no process of the browser's tree listening on any socket while it ran (it talks to Halo over a pipe
on every system); after halo ended, no process and no profile folder left. First the same with halo ended HARD in the
middle (RC-BROWSERHOLD: open, then the model's next call held): the browser is gone 5 s later, and the next session's
start removes the folder a hard end could not. With `--browser none`, or no browser installed, it is reported the way
the other steps that need a browser are (core.browser)."""
from __future__ import annotations

import http.server
import os
import subprocess
import sys
import threading
import time
from pathlib import Path

from realcheck import core, fakes, procs
from realcheck.core import Fail, excerpt

PAGE = (b"<!doctype html><title>Realcheck browser page</title><body><h1>Hello from realcheck</h1><p id='s'>before</p>"
        b"<button onclick=\"document.getElementById('s').textContent = '" + fakes.BROWSER_AFTER.encode() +
        b"'\">Press me</button></body>")
PNG = b"\x89PNG\r\n\x1a\n"


class _Page:
    """The page on 127.0.0.1 (port 0) while the `with` lasts."""

    def __enter__(self) -> str:
        class H(http.server.BaseHTTPRequestHandler):
            def do_GET(self):
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(PAGE)))
                self.end_headers()
                self.wfile.write(PAGE)

            def log_message(self, *a):
                pass
        self.srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), H)
        self.th = threading.Thread(target=self.srv.serve_forever, daemon=True, name="realcheck-browser-page")
        self.th.start()
        return f"http://127.0.0.1:{self.srv.server_address[1]}/page.html"

    def __exit__(self, *exc):
        self.srv.shutdown()
        self.srv.server_close()
        self.th.join(10)


def browser_pids(folder: Path) -> list:
    """The processes whose command line names the home's browser folder (its profile is in it)."""
    want = procs.norm(str(folder))
    return [p for p in procs.snapshot().values() if want and want in procs.norm(p.cmdline)]


def listening(pids) -> list:
    """The listening sockets owned by `pids` (Linux: ss; Windows: netstat; macOS: lsof)."""
    pids = {int(p) for p in pids}
    try:
        if sys.platform.startswith("linux"):
            text = subprocess.run(["ss", "-ltnupH"], capture_output=True, text=True, timeout=20).stdout
            return [ln for ln in text.splitlines() if any(f"pid={p}," in ln for p in pids)]
        if sys.platform == "win32":
            text = subprocess.run(["netstat", "-ano"], capture_output=True, text=True, timeout=60).stdout
            return [ln for ln in text.splitlines() if "LISTENING" in ln and ln.split() and ln.split()[-1].isdigit()
                    and int(ln.split()[-1]) in pids]
        text = subprocess.run(["lsof", "-nP", "-iTCP", "-sTCP:LISTEN"], capture_output=True, text=True,
                              timeout=20).stdout
        return [ln for ln in text.splitlines()[1:] if len(ln.split()) > 1 and ln.split()[1].isdigit()
                and int(ln.split()[1]) in pids]
    except FileNotFoundError as e:
        return [f"cannot look: {e}"]


def judge(reply: str, pictures: list, listeners: list, left_hard: list, left: list, folders: list) -> list:
    """The step's verdict on what it saw: the problems, in plain words ([] passes)."""
    bad = []
    if fakes.BROWSER_DONE not in reply or fakes.BROWSER_AFTER not in reply:
        bad.append(f"the reply does not carry the page's text after the click: {excerpt(reply, 160)!r}")
    if not pictures:
        bad.append("no PNG of the page in the session's attachments folder")
    if listeners:
        bad.append(f"the browser's tree listened on a socket: {listeners[:2]}")
    if left_hard:
        bad.append(f"a hard end of halo left {len(left_hard)} browser process(es) 5 s later: {left_hard[:2]}")
    if left:
        bad.append(f"after halo ended {len(left)} process(es) still ran: {left[:2]}")
    if folders:
        bad.append(f"a browser profile folder was left: {folders[:2]}")
    return bad


def browser(ctx):
    exe = core.browser(ctx)  # --browser none: Skip; a named one that is not there, or none installed: Fail
    h = ctx.home("browser")
    env = ctx.env(h, HALO_CHROME=exe or None)
    if sys.platform == "win32":
        for sub in ("Local", "Roaming"):  # a real Windows home has these; the browser waits for ever without them
            (h.home / "AppData" / sub).mkdir(parents=True, exist_ok=True)
    folder = h.state / "browser"
    r = ctx.run(h, "config", "set", "browser.profile", "clean", env=env, timeout=60)
    if r.code != 0:
        raise Fail(f"`halo config set browser.profile clean` exit {r.code}: {excerpt(r.err, 160)!r}")
    ev: dict = {}
    with _Page() as url:
        # 1. halo ended hard while its browser runs: the browser goes with it. The provider's gate is armed afresh: an
        # earlier step's release() leaves it open, and an open gate holds nothing (the full run on the Linux VM)
        ctx.provider.rearm()
        p = subprocess.Popen(ctx.argv("-p", f"RC-BROWSERHOLD url={url}", "--permission-mode", "auto"), cwd=str(h.proj),
                             env=env, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        ctx._mark(h, p.pid)
        listeners, left_hard = [], []
        try:
            got = core.wait_until(lambda: "RC-BROWSERHOLD" in ctx.provider.hung and browser_pids(folder), 90, 0.5)
            if not got:
                raise Fail("the held session's browser never ran (no process named its profile in 90 s)")
            pids = [q.pid for q in browser_pids(folder)]
            ev["browser_processes"] = len(pids)
            listeners = listening(pids)
            p.kill()
            p.wait(30)
            end = time.monotonic() + 5.0
            left_hard = browser_pids(folder)
            while left_hard and time.monotonic() < end:
                time.sleep(0.25)
                left_hard = browser_pids(folder)
            left_hard = [q.short(90) for q in left_hard]
        finally:
            if p.poll() is None:
                p.kill()
            ctx.provider.release()
            ctx.provider.rearm()
        # 2. the whole thing, ended the normal way
        r = ctx.run(h, "-p", f"RC-BROWSER url={url}", "--permission-mode", "auto", env=env, timeout=150)
    ev.update(seconds=round(r.seconds, 1), code=r.code)
    if r.code != 0:
        raise Fail(f"`halo -p` with the Browser tool exit {r.code}: {excerpt(r.out, 160)!r} {excerpt(r.err, 200)!r}", ev)
    pictures = [q for q in (h.state / "attachments").glob("*/page-*.png") if q.read_bytes()[:8] == PNG]
    left = [q.short(90) for q in ctx.left_after(h, 5.0)]
    folders = [q.name for q in folder.glob("clean-*")] if folder.is_dir() else []
    ev.update(pictures=len(pictures), listeners=listeners, left_hard=left_hard, left=left, folders=folders)
    bad = judge(r.out, pictures, listeners, left_hard, left, folders)
    if bad:
        if left:
            ev["ended"] = ctx.end_leftovers(h)
        raise Fail("; ".join(bad), ev)
    return (f"opened, pressed and pictured a real page in {os.path.basename(exe or 'the browser')}; "
            f"{len(pictures)} picture(s); nothing left after a normal and a hard end"), ev
