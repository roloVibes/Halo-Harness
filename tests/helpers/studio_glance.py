"""tests.helpers.studio_glance -- the glance and the alert (Halo 3.4.1.0 R4) in headless Chrome on the driver base, over
tests/helpers/glance_rig.py (a scratch home, every pack off, one fake session behind its real control socket). A stub
stands in for the browser's Notification before any page script runs (it records each permission ask and each
notification) and counts the page's reads of the attention queue. tests/test_studio_glance_page.py reads it:

    python -m tests.helpers.studio_glance

`door`: Session's "..." -> Open the glance: the dialog says where the glance is (this machine's address, the phone's line).
`setting`: Settings -> Studio -> Alerts: nothing asked on load; None is the choice; a click on the browser's asks ONCE, saves
`studio.alerts: browser`, says this browser allows it.
`alert`: a permission card starts waiting: ONE notification naming what waits and the session; the queue read twice more
and the ask's frames again: still one. A click on it opens Session's Attention on that row.
`glance`: at 390 px wide: no horizontal scroll, the sentence, the ask with its answers as large buttons, the spend ("no cap
set"), the elapsed time, the last events; Allow once answers the card through the owner-proof path; then nothing waits.
`stale`: Studio stops: the page says it is stale; Studio comes back on its port: the page is live again by itself.
The last stdout line is a JSON object of what it saw (exit 2: no Chrome). No model is called.
"""
from __future__ import annotations

import json
import sys
import time
from contextlib import contextmanager
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "tools"))

from tests.helpers.chrome_driver import Driver  # noqa: E402

Q = "document.querySelector"
QA = "document.querySelectorAll"
STUB = """(() => {
  const notes = [], asks = [], reads = [];
  class FakeNote { constructor(title, opts) { this.title = title; this.body = (opts || {}).body || ""; this.tag = (opts || {}).tag || "";
    this.onclick = null; this.closed = false; notes.push(this); } close() { this.closed = true; } }
  FakeNote.permission = "default";
  FakeNote.requestPermission = () => { asks.push(Date.now()); FakeNote.permission = "granted"; return Promise.resolve("granted"); };
  Object.defineProperty(window, "Notification", { value: FakeNote, configurable: true, writable: true });
  const f = window.fetch.bind(window);
  window.fetch = (u, init) => { const s = String(u && u.href || u); if (s.includes("/api/fleet/attention") && !s.includes("answer")) reads.push(Date.now()); return f(u, init); };
  window.__notes = notes; window.__asks = asks; window.__reads = reads;
})();"""
GLANCE = f"{Q}('[data-testid=\"glance\"]')"
ASK = f"{Q}('[data-testid=\"glance-ask\"][data-kind=\"permission\"]')"


def _open(c, url: str, ready: str) -> None:
    c.go("about:blank")  # a navigation to the same address with a #t= fragment is a fragment hop
    c.go(url)
    c.wait(ready, 40)


def door(c, rig) -> dict:
    _open(c, rig.url("mode=session"), f"{QA}('[data-testid=\"section-tab\"]').length > 0 && !!{Q}('[data-testid=\"section-more\"]')")
    c.click_on(f"{Q}('[data-testid=\"section-more\"]')")
    c.wait(f"!!{Q}('[data-testid=\"session-glance\"]')", 15)
    c.click_on(f"{Q}('[data-testid=\"session-glance\"]')")
    body = f"{Q}('[data-testid=\"glance-door-body\"]')"
    c.wait(f"!!{body}", 20)
    out = {"door_ssh": c.js(f"{body}.dataset.ssh"), "door_line": c.js(f"{Q}('[data-testid=\"glance-door-line\"]').textContent"),
           "door_here": c.js(f"{body}.querySelector('.gz-addr').textContent"),
           "door_cost": c.js(f"[...{QA}('[data-testid=\"glance-door\"] [data-testid=\"dialog-cost\"] dd')].map((d) => d.textContent)")}
    c.key("Escape")
    c.wait(f"!{Q}('[data-testid=\"glance-door\"]')", 10)
    return out


def setting(c, rig) -> dict:
    block = f"{Q}('[data-testid=\"settings-alerts\"]')"
    _open(c, rig.url("mode=settings&group=studio"), f"!!{block} && {block}.dataset.choice === 'none'")
    out = {"asked_on_load": c.js("window.__asks.length"), "notes_on_load": c.js("window.__notes.length"),
           "choices": c.js(f"[...{QA}('[data-testid=\"settings-alerts-choice\"]')].map((b) => b.dataset.id)")}
    c.click_on(f"{Q}('[data-testid=\"settings-alerts-choice\"][data-id=\"browser\"]')")
    c.wait(f"{block}.dataset.choice === 'browser' && {Q}('[data-testid=\"settings-alerts-state\"]')?.dataset.state === 'ready'", 20)
    out["asked_after_click"] = c.js("window.__asks.length")
    cfg = json.loads((rig.state / "config.json").read_text(encoding="utf-8"))
    out["saved"] = (cfg.get("studio") or {}).get("alerts")
    out["state_line"] = c.js(f"{Q}('[data-testid=\"settings-alerts-state\"]').textContent")
    return out


def alert(c, rig) -> dict:
    before = c.js("window.__reads.length")
    rig.ask("ask")  # the fake session parks on permission card perm_1
    c.wait("window.__notes.length >= 1", 40)
    n = c.js("window.__notes[0] && {title: window.__notes[0].title, body: window.__notes[0].body, tag: window.__notes[0].tag}")
    # the same ask said again by its frames, and the queue read twice more: still ONE notification
    rig.server.events.publish({"session_id": rig.sid, "event": "permission_request", "agent_id": None, "turn": 1, "ts": time.time(),
                               "data": {"id": "perm_1", "name": "Bash", "input": {"command": "echo hi"}}})
    rig.server.events.publish({"session_id": None, "event": "fleet", "agent_id": None, "turn": None, "ts": time.time(),
                               "data": {"action": "attention", "count": 1}})
    reads = c.js("window.__reads.length")
    c.wait(f"window.__reads.length >= {reads + 2}", 40)
    out = {"note": n, "notes_after": c.js("window.__notes.length"), "reads_grew": c.js("window.__reads.length") > before}
    c.js("window.__notes[0].onclick()")
    row = f"{Q}('[data-panel=\"session-attention\"] [data-testid=\"fleet-attn-row\"][aria-selected=\"true\"]')"
    c.wait(f"!!{Q}('.section-view[data-section=\"session\"]:not([hidden])') && !!{row}", 30)
    out["opened"] = c.js(f"{row}.dataset.kind")
    out["note_closed"] = c.js("window.__notes[0].closed")
    return out


def glance(c, rig) -> dict:
    c.call("Emulation.setDeviceMetricsOverride", width=390, height=844, deviceScaleFactor=2, mobile=True)
    _open(c, rig.url("mode=glance"), f"!!{ASK} && {Q}('[data-testid=\"glance-status\"]')?.dataset.state === 'live'")
    keys = f"[...{ASK}.querySelectorAll('[data-testid=\"glance-key\"]')]"
    out = {"rail": c.js(f"!!{Q}('.rail') || !!{Q}('[data-testid=\"section-tab\"]')"),
           "scroll": c.js("[document.documentElement.scrollWidth, document.documentElement.clientWidth, "
                          f"{Q}('.gz').scrollWidth, {Q}('.gz').clientWidth]"),
           "narration": c.wait(f"{Q}('[data-testid=\"glance-narration\"]')?.textContent", 20),
           "spend": c.js(f"{Q}('[data-testid=\"glance-spend\"] dd').textContent"),
           # 3.4.1.0 R5: a loaded box drew "no session" before the session's row landed: wait for the value asserted
           "elapsed": c.wait(f"(() => {{ const t = {Q}('[data-testid=\"glance-elapsed\"] dd')?.textContent; "
                             "return t && t !== 'no session' ? t : ''; })()", 20),
           "keys": c.js(f"{keys}.map((b) => [b.dataset.key, b.querySelector('.gz-key-word').textContent, b.querySelector('.gz-key-does').textContent])"),
           "key_h": c.js(f"Math.min(...{keys}.map((b) => b.getBoundingClientRect().height))"),
           "ask_what": c.js(f"{ASK}.querySelector('.gz-ask-what').textContent"),
           "notes_on_load": c.js("window.__notes.length"), "asked_on_load": c.js("window.__asks.length")}
    out["events_on_load"] = c.js(f"[...{QA}('[data-testid=\"glance-event\"]')].map((e) => e.textContent)")
    for i, (event, data) in enumerate((("text_chunk", {"text": "Reading the basket first."}), ("tool_use_start", {"id": "c1", "name": "Read"}),
                                       ("text_chunk", {"text": "The discount applies before tax."}), ("tool_use_start", {"id": "c2", "name": "Bash"}))):
        rig.frame(event, data, i)
    out["events"] = c.wait(f"{QA}('[data-testid=\"glance-event\"]').length === 3 && [...{QA}('[data-testid=\"glance-event\"]')]"
                           ".map((e) => e.dataset.kind + ': ' + e.querySelector('.gz-ev-what').textContent)", 20)
    c.click_on(f"{ASK}.querySelector('[data-testid=\"glance-key\"][data-key=\"a\"]')")
    deadline = time.time() + 30
    while rig.decision("perm_1") is None and time.time() < deadline:
        time.sleep(0.1)
    d = rig.decision("perm_1")
    out["decision"] = getattr(d, "action", None) or str(d)
    out["after"] = c.wait(f"!!{Q}('[data-testid=\"glance-asks-none\"]') && {Q}('[data-testid=\"glance-asks-none\"]').textContent", 30)
    return out


def stale(c, rig) -> dict:
    status = f"{Q}('[data-testid=\"glance-status\"]')"
    rig.stop_studio()
    out = {"stale": c.wait(f"{status}.dataset.state === 'stale' && {status}.textContent", 60)}
    rig.restart()
    out["back"] = c.wait(f"{status}.dataset.state === 'live' && {status}.textContent", 60)
    return out


class GlanceDriver(Driver):
    no_chrome = {"skip": "no Chrome found"}

    @contextmanager
    def session(self, c):
        from tests.helpers.glance_rig import GlanceRig
        c.call("Page.enable")  # the stub runs before any page script of every page that loads after it
        c.call("Page.addScriptToEvaluateOnNewDocument", source=STUB)
        rig = GlanceRig()
        try:
            yield ((door, (c, rig)), (setting, (c, rig)), (alert, (c, rig)), (glance, (c, rig)), (stale, (c, rig)))
        finally:
            rig.close()


if __name__ == "__main__":
    sys.exit(GlanceDriver(sys.argv[1:]).main())
