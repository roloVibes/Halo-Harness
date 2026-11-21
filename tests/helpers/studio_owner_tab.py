"""tests.helpers.studio_owner_tab -- "Make this tab yours" (Halo 3.6.0.6 P, the owner's point 31) in headless Chrome,
over tests/helpers/crew_rig.py with the pack that ships with Halo (doc-review) installed and enabled. Every press is a
real one (the DevTools input domain), never a scripted click, except where a step proves a scripted click does nothing.
tests/test_studio_owner_tab.py reads what it saw:

    link      Studio opened as the launcher does; a link in the page pressed to Agents -> 2 · Workflows with the pack's
              workflow open: the notice row and its button from the first draw (its height and the header's top kept),
              VIEW ONLY in the status bar; Try it -> POST crew/try 403 and the one toast with the same button
    press     the row's button pressed: the tab reloads, no row, no VIEW ONLY; Try it -> POST crew/try 200, its result
    scripted  a link again; a scripted click() on the button: no reload, the row stays
    toast     on that tab, Try it -> the toast's own button pressed: the tab reloads and Try it answers 200
    restarted (3.6.0.6 PF) Studio started again on the same port (a new key; the old server's kept connections ended,
              as a real restart ends them with its process) and its new address entered over the tab: no reload, the
              row says "Studio was started again"; its button pressed: Try it answers 200

The last stdout line is a JSON object of what it saw (exit 2: no Chrome). No model is called beyond the mock upstream.

    python -m tests.helpers.studio_owner_tab
"""
from __future__ import annotations

import sys
import time
from contextlib import contextmanager
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from tests.helpers.chrome_driver import Driver  # noqa: E402

FLOW = "doc-review--review-docs"
Q = "document.querySelector"
ROW = f"{Q}('[data-testid=\"owner-tab-row\"]')"
TOAST = f"{Q}('[data-testid=\"owner-toast\"]')"
FORM = f"{Q}('[data-testid=\"flow-form\"][data-name=\"{FLOW}\"]')"
# what each write answered (the shell takes fetch at boot, so this runs before it on every new document), and the
# notice row's height and the header's top at the shell's first draw
WATCH = """(() => {
  window.__w = [];
  const f = window.fetch;
  window.fetch = async function (u, init) {
    const r = await f.apply(this, arguments);
    const m = (init && init.method) || 'GET';
    if (m !== 'GET') window.__w.push(m + ' ' + new URL(String(u), location.href).pathname.replace('/api/', '') + ' ' + r.status);
    return r;
  };
  const look = () => {
    const top = document.querySelector('.topbar');
    if (!top) return requestAnimationFrame(look);
    const row = document.querySelector('[data-testid="owner-tab-row"]');
    window.__first = {row: row ? row.getBoundingClientRect().height : -1, top: top.getBoundingClientRect().top};
  };
  requestAnimationFrame(look);
})();"""


def writes(c, part: str) -> list:
    return c.js(f"(window.__w || []).filter((w) => w.includes({part!r}))")


def landed(c, timeout: float = 40) -> None:
    """A new document of the shell, the pack's workflow open in the form."""
    c.wait(f"!window.__before && document.readyState === 'complete' && !!{FORM} && !!window.__first", timeout)


def by_link(c, rig) -> None:
    """A link in the page, pressed: a same-origin navigation the server gives no proof."""
    href = f"/?mode=agents&view=workflows&workflow={FLOW}&tour=off"
    c.js(f"(() => {{ const a = document.createElement('a'); a.href = {href!r}; a.textContent = 'to Workflows';"
         " a.dataset.testid = 'test-link'; a.style.cssText = 'position:fixed;left:300px;top:300px;z-index:2147483647;"
         "padding:8px;background:#fff;color:#000'; document.body.append(a); window.__before = 1; return 1; })()")
    c.click_on(f"{Q}('[data-testid=\"test-link\"]')")
    landed(c)


def try_it(c, text: str) -> None:
    c.wait(f"!!{Q}('[data-testid=\"flow-try-text\"]')", 20)
    c.click_on(f"{Q}('[data-testid=\"flow-try-text\"]')")
    c.js(f"{Q}('[data-testid=\"flow-try-text\"]').select && {Q}('[data-testid=\"flow-try-text\"]').select(); 1")
    c.call("Input.insertText", text=text)
    c.wait(f"!!{Q}('[data-testid=\"flow-try-send\"]') && !{Q}('[data-testid=\"flow-try-send\"]').disabled", 20)
    c.click_on(f"{Q}('[data-testid=\"flow-try-send\"]')")


def notice(c) -> dict:
    return c.js(f"""(() => {{ const r = {ROW}; const b = r && r.querySelector('button');
      const cell = {Q}('[data-testid="owner-note"]'); const top = {Q}('.topbar');
      return {{row: r ? r.querySelector('[data-testid="owner-tab-line"]').innerText : null, button: b ? b.innerText : null,
              hover: b ? b.title : null, cell: cell ? cell.innerText : null, cell_hover: cell ? cell.closest('[title]')?.title : null,
              first: window.__first, now: {{row: r ? r.getBoundingClientRect().height : -1, top: top.getBoundingClientRect().top}}}}; }})()""")


def toast(c) -> dict:
    return c.js(f"""(() => {{ const t = {TOAST}; const b = t && t.querySelector('[data-testid="owner-tab-yours"]');
      return {{line: t ? t.querySelector('[data-testid="owner-tab-line"]').innerText : null, button: b ? b.innerText : null,
              count: document.querySelectorAll('[data-testid="owner-toast"]').length,
              others: [...document.querySelectorAll('.toast')].filter((x) => !x.matches('[data-testid="owner-toast"]')).map((x) => x.innerText)}}; }})()""")


def link(c, rig) -> dict:
    by_link(c, rig)
    out = {"link": notice(c)}
    try_it(c, "Review notes.md")
    c.wait(f"!!{TOAST} && (window.__w || []).some((w) => w.startsWith('POST crew/try '))", 30)
    time.sleep(1.0)  # a view's own toast of the same refusal, if any, lands too: it must fold into the one
    out["link_try"] = writes(c, "crew/try")
    out["link_toast"] = toast(c)
    return out


def press(c, rig) -> dict:
    c.js("window.__before = 1; 1")
    c.click_on(f"{ROW}.querySelector('[data-testid=\"owner-tab-yours\"]')")
    landed(c)
    out = {"pressed": notice(c)}
    try_it(c, "Review notes.md")
    c.wait(f"{Q}('[data-testid=\"flow-try-state\"]')?.textContent === 'done' || {Q}('[data-testid=\"flow-try-state\"]')?.textContent === 'failed'", 180)
    out["pressed_try"] = writes(c, "crew/try")
    out["pressed_state"] = c.js(f"{Q}('[data-testid=\"flow-try-state\"]').textContent")
    return out


def scripted(c, rig) -> dict:
    by_link(c, rig)
    c.js(f"window.__before = 1; {ROW}.querySelector('[data-testid=\"owner-tab-yours\"]').click(); 1")
    time.sleep(2.0)  # a reload would have started by now: the mark would be gone
    return {"scripted": {"reloaded": c.js("window.__before !== 1"), "row": c.js(f"!!{ROW}")}}


def from_toast(c, rig) -> dict:
    try_it(c, "Review notes.md")
    c.wait(f"!!{TOAST}", 30)
    out = {"toast_before": toast(c)}
    c.js("window.__before = 1; 1")
    c.click_on(f"{TOAST}.querySelector('[data-testid=\"owner-tab-yours\"]')")
    landed(c)
    out["toast_after"] = notice(c)
    try_it(c, "Review notes.md")
    c.wait("(window.__w || []).some((w) => w.startsWith('POST crew/try '))", 30)
    out["toast_try"] = writes(c, "crew/try")
    return out


def kept_sockets(server) -> list:
    """The connections `server` accepted: a real restart ends them with its process, so an in-process one ends them too."""
    socks, take = [], server.process_request

    def process_request(request, addr):
        socks.append(request)
        return take(request, addr)
    server.process_request = process_request
    return socks


def restarted(c, rig) -> dict:
    """3.6.0.6 PF: Studio started again on the SAME port under his open tab (a new key), and its new address entered
    over the tab: only the fragment differs, so the browser does not reload and the page takes the new key."""
    import socket
    import threading
    from halo_harness.studio.events import bridge_for
    from halo_harness.studio.server import start_server
    old = rig.server
    port = old.server_address[1]
    for fn in (old.shutdown, old.server_close):
        fn()
    for s in old.kept:
        try:
            s.shutdown(socket.SHUT_RDWR)
        except OSError:
            pass
    rig.server = start_server(port=port, cwd=rig.proj, state_dir=rig.state)
    rig.server.kept = kept_sockets(rig.server)
    threading.Thread(target=rig.server.serve_forever, daemon=True, name="crew-studio-again").start()
    bridge_for(rig.server)
    c.js("window.__before = 1; 1")
    c.go(c.js("location.href.split('#')[0]") + "#t=" + rig.server.token)  # the new address, entered over the tab
    c.wait(f"!!{ROW}", 30)
    out = {"again": notice(c), "again_reloaded": c.js("window.__before !== 1")}
    c.click_on(f"{ROW}.querySelector('[data-testid=\"owner-tab-yours\"]')")
    landed(c)
    out["again_pressed"] = notice(c)
    try_it(c, "Review notes.md")
    c.wait("(window.__w || []).some((w) => w.startsWith('POST crew/try '))", 30)
    out["again_try"] = writes(c, "crew/try")
    return out


class OwnerTabDriver(Driver):
    no_chrome = {"skip": "no Chrome found"}
    width, height = 1500, 900

    @contextmanager
    def session(self, c):
        from tests.helpers.crew_rig import CrewRig
        from tests.helpers.studio_session import collect_page_errors
        with CrewRig() as rig:
            rig.with_pack().studio()
            rig.server.kept = kept_sockets(rig.server)
            collect_page_errors(c)
            c.call("Page.addScriptToEvaluateOnNewDocument", source=WATCH)
            c.go(rig.url(f"&view=workflows&workflow={FLOW}"))  # as the launcher opens it: the owner's own page
            c.wait(f"document.readyState === 'complete' && !!{FORM}", 40)
            self.out["own_page"] = c.js(f"!{ROW} && !{Q}('[data-testid=\"owner-note\"]')")
            yield ((link, (c, rig)), (press, (c, rig)), (scripted, (c, rig)), (from_toast, (c, rig)), (restarted, (c, rig)),
                   (errors, (c,)))


def errors(c) -> dict:
    from tests.helpers.studio_session import page_errors
    return {"page_errors": page_errors(c)}


if __name__ == "__main__":
    sys.exit(OwnerTabDriver(sys.argv[1:]).main())
