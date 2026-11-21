"""tests.helpers.studio_browser_tool -- 3.6.0.6 W batch 2 entry 2 (the owner: "FULLY CONTROL A BROWSER AND SEE IT"),
real clicks in headless Chrome on the driver base, over tests/helpers/headless_rig.py (an in-process Studio whose own
launcher spawns `halo --headless --session-for studio` on the fake upstream):

    python -m tests.helpers.studio_browser_tool browser

Session's Start view -> New session (nothing set up for a browser) -> a turn typed in the Prompt whose fake model
calls Browser open (a page this helper serves on 127.0.0.1), click, screenshot: the reply names the page's text after
the click; Session's Live column has one row per call in the tool's words; a click on the click step's row opens its
detail on THE PAGE'S PICTURE (a PNG, its size not zero); End session -> no process carries the session's browser
profile. The last stdout line is a JSON object of what it saw (exit 2: no Chrome). Every child is ended by the rig."""
from __future__ import annotations

import http.server
import json
import os
import sys
import threading
import time
from contextlib import contextmanager
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from tests.helpers.chrome_driver import Driver  # noqa: E402
from tests.helpers.studio_headless import end_it, start_one, typed  # noqa: E402

ASK = "open the browser page"
DONE = "browser done:"
PAGE = (b"<!doctype html><title>Studio browser page</title><body><h1>Hello from the Studio page</h1>"
        b"<p id='s'>before</p><button onclick=\"document.getElementById('s').textContent = 'after the press'\">"
        b"Press me</button></body>")
ROWS = "[...document.querySelectorAll('[data-testid=\"session-live-tool\"]')]"


class _Page:
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
        from halo_harness.http_bind import ThreadingHTTPServer  # binds without a reverse name lookup (tests/test_http_bind.py)
        self.srv = ThreadingHTTPServer(("127.0.0.1", 0), H)
        self.th = threading.Thread(target=self.srv.serve_forever, daemon=True, name="studio-browser-page")
        self.th.start()
        return f"http://127.0.0.1:{self.srv.server_address[1]}/page.html"

    def __exit__(self, *exc):
        self.srv.shutdown()
        self.srv.server_close()
        self.th.join(10)


def scenario(url: str):
    """The fake model: a turn saying ASK calls Browser open, click, screenshot, then answers DONE + the click's line."""
    from tests.helpers.mock_openai import _finish
    from tests.helpers.session_rig import text_step, tool_step
    steps = [{"action": "open", "url": url}, {"action": "click", "target": "Press me"}, {"action": "screenshot"}]

    def step(handler, body) -> None:
        from tests.helpers.headless_rig import _texts
        msgs = [m for m in (body or {}).get("messages") or [] if isinstance(m, dict)]
        last_user = max((i for i, m in enumerate(msgs) if m.get("role") == "user"), default=-1)
        said = _texts(body)
        results = [m for m in msgs[last_user + 1:] if m.get("role") == "tool"]
        if ASK not in said:
            return _finish(handler, text_step("pong"))
        if len(results) < len(steps):
            return _finish(handler, tool_step(("Browser", steps[len(results)], f"call_sb_{len(results)}")))
        click = str(results[1].get("content") if len(results) > 1 else "")
        line = next((ln for ln in click.splitlines() if "after the press" in ln), "(no such line)")
        return _finish(handler, text_step(f"{DONE} {line}"))
    return step


def _profile_pids(needle: str) -> list:
    from tests.helpers.leftovers import scan
    want = os.path.normpath(needle)
    out = []
    for p in scan(lambda _pid, _start: True).values():
        cmd = p.cmd or ""
        if (want.lower() in cmd.replace("/", os.sep).lower()) if os.name == "nt" else (want in cmd):
            out.append(p.pid)
    return out


def browse(c, rig, server, url) -> dict:
    out = start_one(c, rig, server)
    typed(c, ASK)
    texts = "[...document.querySelectorAll('[data-testid=\"prompt-text\"]')].map((x) => x.textContent).join(' ')"
    out["reply"] = c.wait(f"{texts}.includes({json.dumps(DONE)}) && {texts}", 120)
    words = f"{ROWS}.map((r) => r.innerText.replace(/\\s+/g, ' ').trim())"
    try:
        out["rows"] = c.wait(f"{words}.filter((t) => t.includes('Browser')).length >= 3 && {words}", 30)
    except TimeoutError:
        out["rows"] = c.js(words)
    row = f"{ROWS}.find((r) => r.innerText.replace(/\\s+/g, ' ').includes('Browser click'))"
    out["profile_pids_running"] = len(_profile_pids(str(rig.state / "browser")))
    if not c.js(f"!!{row}"):
        out["live_text"] = c.js("(document.querySelector('[data-testid=\"session-live\"]') || document.body)"
                                ".innerText.slice(0, 1500)")
        return out
    c.click_on(row)
    shot = f"{row}.parentElement.querySelector('[data-testid=\"session-live-shot\"]')"
    try:
        c.wait(f"!!{shot}", 30)
    except TimeoutError:
        import urllib.request
        req = urllib.request.Request(f"http://127.0.0.1:{server.server_address[1]}/api/sessions/{out['sid']}/attachments/"
                                     f"page-2.png", headers={"Authorization": "Bearer " + server.token})
        try:
            with urllib.request.urlopen(req, timeout=10) as r:
                route = [r.status, r.headers.get("Content-Type"), len(r.read())]
        except Exception as e:
            route = [f"{type(e).__name__}: {e}"]
        out["shot_diag"] = {"route": route, "open": c.js(f"{row}.parentElement.dataset.open || ''"),
                            "frame": c.js(f"!!{row}.parentElement.querySelector('.slv-shot')"),
                            "full": c.js(f"({row}.parentElement.querySelector('pre') || {{}}).textContent?.slice(-300)")}
        return out
    out["shot"] = c.wait(f"{shot} && {shot}.naturalWidth > 0 && [{shot}.dataset.type, Number({shot}.dataset.bytes), "
                         f"{shot}.naturalWidth, {shot}.naturalHeight, {shot}.getBoundingClientRect().width, "
                         f"{shot}.closest('.slv-tool').getBoundingClientRect().width]", 30)
    out["magic"] = c.js(f"Array.from(atob({shot}.src.split(',')[1]).slice(0, 8)).map((ch) => ch.charCodeAt(0))")
    return out


def end_and_look(c, rig, server) -> dict:
    out = end_it(c, rig, server)
    needle = str(rig.state / "browser")
    end = time.monotonic() + 10
    left = _profile_pids(needle)
    while left and time.monotonic() < end:
        time.sleep(0.25)
        left = _profile_pids(needle)
    out["browser_left"] = left
    return out


class BrowserDriver(Driver):
    no_chrome = {"skip": "no Chrome found"}

    @contextmanager
    def session(self, c):
        from tests.helpers.headless_rig import HeadlessRig
        from tests.helpers.mock_openai import SCENARIOS
        with _Page() as url, HeadlessRig() as rig:
            SCENARIOS["headless"] = scenario(url)
            rig.spawn_env()
            server = rig.studio()
            yield ((browse, (c, rig, server, url)), (end_and_look, (c, rig, server)))


if __name__ == "__main__":
    sys.exit(BrowserDriver(sys.argv[1:]).main())
