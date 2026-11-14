"""tests.helpers.studio_density -- Halo 3.3.16.0 R1b, the density pass ("small blocks that make it hard to use ... needs
a review to make studio cleaner and clearer", the owner 2026-11-09): every core section opened in headless Chrome over
the seeded homes the existing drivers use -- Session and Agents -> Live (`?mode=agents`, 3.3.16.0 R2) over the
Prompt rig's live session
(tests/helpers/prompt_rig.py), the rest over tools/capture_studio.seeded_home (the edit driver's), each an in-process
Studio -- and measured with getBoundingClientRect where the primitives mark themselves:

    [data-density=bar]   a control bar: a panel's title bar (lib/workspace/Panel.tsx), Tabs (lib/ui/Tabs.tsx), the
                         header (shell/Header.tsx), a section's bar (Agents' view switch), an inspector page's head or
                         a form's button row -- each >= 36 px tall
    [data-density=row]   a row that is a target: an inspector Edit row, a page rail's item -- each >= 40 px
    [data-density=body]  a panel's body: its inset (its own padding, plus its one child's when it draws edge to edge)
                         >= 12 px on every side
and, per section, the panels open on load (one main thing per view, 3.6.0.0 R0a: the stage) and the gaps between the
open panels (>= 12 px); then each closed panel opened from the view bar in turn (3.6.0.0 R0a: the strips went).
Agents is opened on Cast and Live (3.4.0.0 D: Runs went); Cast once more with `?edit=lineup:halo-dev-cycle`
(the inspector's summary, then one block's page). 3.3.16.0 R2: Setup -> Machines, and Live on the fleet once more with
the Attention queue open (the chip) and the inspector's glance.

    python -m tests.helpers.studio_density        the JSON of what it saw on the last stdout line (exit 2: no Chrome)
    python -m tests.helpers.studio_density DIR    the same, and a capture of each section into DIR

tests/test_studio_density.py reads it. No model is called."""
from __future__ import annotations

import shutil
import sys
import threading
import time
from contextlib import contextmanager
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "tools"))

from tests.helpers.chrome_driver import Driver  # noqa: E402

SHOTS: list = []

# (name, mode, extra query) -- the six sections, Agents on Cast and Live, idle and busy (3.4.0.0 D: Runs went)
SECTIONS = (("session", "session", ""), ("agents-cast", "agents", "&view=cast"),
            ("agents-live", "agents", "&view=live"), ("agents-busy", "agents", "&view=live"), ("packs", "packs", ""), ("setup", "setup", ""),
            ("settings", "settings", ""), ("local", "local", ""))

# what each section draws once it is there (the measure waits for it, then for two equal reads)
# 3.3.18.0: a view of Agents is ready when its workspace has laid out a cell AND drawn what the view shows (Live over this
# seeded home: its one empty sentence), never on its bar alone (a Windows runner measured Live's 0 of 0 panels once)
READY = {"session": ".ws-cell", "agents-busy": "[data-testid=roles-live-map]",
         "agents-cast": "[data-part=roles] [data-testid=roles-canvas], [data-part=roles] [data-testid=roles-start]",
         "agents-live": ".ws-cell [data-testid=roles-live-empty]", "packs": ".ws-cell", "setup": "[data-testid=setup-rail]",
         "settings": "[data-testid=settings-rail-group]", "local": "[data-testid=local-rail-page]"}

MEASURE = r"""(() => {
  const vis = (el) => { const r = el.getBoundingClientRect(); return r.width > 0 && r.height > 0 && !el.closest('[hidden]'); };
  // a row is named by its own testid or its first control's (an Edit row: roles-block-<name>); a bar by the nearest
  const name = (el, down) => el.dataset.testid || (down && el.querySelector('[data-testid]')?.dataset.testid)
    || el.closest('[data-testid]')?.dataset.testid || el.className || el.tagName;
  const all = (k) => [...document.querySelectorAll(`[data-density="${k}"]`)].filter(vis);
  const h = (el) => Math.round(el.getBoundingClientRect().height * 10) / 10;
  const pad = (el) => { const cs = getComputedStyle(el); return ['Top', 'Right', 'Bottom', 'Left'].map((k) => parseFloat(cs['padding' + k]) || 0); };
  const inset = (el) => { const own = pad(el), kids = [...el.children].filter(vis);
    if (kids.length === 1) { const c = pad(kids[0]); return Math.min(...own.map((p, i) => p + c[i])); } return Math.min(...own); };
  const ws = [...document.querySelectorAll('.workspace')].find((w) => vis(w) && w.querySelector('.stage-main'));
  const open = ws ? [...ws.querySelectorAll('.stage-main > .ws-cell, .stage-drawer > .ws-cell')].filter(vis) : [];
  const cells = open;
  const ids = ws ? [...open.filter((c) => c.closest('.stage-main')).map((c) => c.dataset.panel),
    ...[...ws.querySelectorAll('[data-testid=viewbar-btn]')].filter((b) => !b.dataset.added).map((b) => b.dataset.panel)] : [];
  const rs = cells.map((c) => c.querySelector(':scope > .panel').getBoundingClientRect());  // the frames, not the cells' gutters
  let gap = 999;
  for (const a of rs) for (const b of rs) {
    if (a === b) continue;
    const row = a.top < b.bottom && b.top < a.bottom, col = a.left < b.right && b.left < a.right;
    if (row && b.left >= a.right - 1) gap = Math.min(gap, b.left - a.right);
    if (col && b.top >= a.bottom - 1) gap = Math.min(gap, b.top - a.bottom);
  }
  return {bars: all('bar').map((el) => [name(el, false), h(el)]), rows: all('row').map((el) => [name(el, true), h(el)]),
          bodies: all('body').map((el) => [el.closest('.ws-cell')?.dataset.panel || name(el, false), inset(el)]),
          open: open.map((c) => c.dataset.panel), ids: [...new Set(ids)], cells: new Set(ids).size,
          gap: cells.length > 1 ? gap : null};
})()"""


def shot(c, name: str) -> None:
    if SHOTS:
        import base64
        data = c.call("Page.captureScreenshot", format="png")["data"]
        (Path(SHOTS[0]) / f"density-{name}.png").write_bytes(base64.b64decode(data))


def settled(c, timeout: float = 20) -> dict:
    """The measure once two reads 400 ms apart agree (a section lays out a moment after its first paint)."""
    end, last = time.time() + timeout, None
    while time.time() < end:
        got = c.js(MEASURE)
        if got == last and got.get("bars"):
            return got
        last = got
        time.sleep(0.4)
    return last or {}


# one workspace panel opened from the view bar: its title bar and its body's inset (then it is closed again)
CELL = """(() => { const cell = [...document.querySelectorAll('.workspace .stage-main > .ws-cell[data-panel="{pid}"], .workspace .stage-drawer > .ws-cell[data-panel="{pid}"]')].find((x) => x.offsetParent);
  const body = cell && cell.querySelector('.panel-body:not([hidden])'), bar = cell && cell.querySelector('.panel-bar');
  if (!body || !body.getBoundingClientRect().height) return null;
  const pad = (el) => { const cs = getComputedStyle(el); return ['Top', 'Right', 'Bottom', 'Left'].map((k) => parseFloat(cs['padding' + k]) || 0); };
  const own = pad(body), kids = [...body.children].filter((k) => k.getBoundingClientRect().height > 0);
  const inset = kids.length === 1 ? Math.min(...own.map((p, i) => p + pad(kids[0])[i])) : Math.min(...own);
  return ['{pid}', Math.round(bar.getBoundingClientRect().height * 10) / 10, inset]; })()"""
STRIP = """(() => { const b = [...document.querySelectorAll('.section-view:not([hidden]) [data-testid=viewbar-btn][data-panel="{pid}"]')].find((x) => x.offsetParent);
  if (!b) return false; b.click(); return b.dataset.role; })()"""
MAIN_BTN = """(() => { const b = document.querySelector('.section-view:not([hidden]) [data-testid=viewbar-btn][data-role=main]'); if (b) b.click(); return 1; })()"""


def each_panel(c, cells: list) -> list:
    """Open each closed panel of the view in turn from its button in the view bar and measure it (a drawer is closed
    again by its button, a tab by the main thing's)."""
    out = []
    for pid in cells:
        was_open = c.js(CELL.replace("{pid}", pid))
        if was_open:
            out.append(was_open)
            continue
        role = c.js(STRIP.replace("{pid}", pid))
        if not role:
            continue
        out.append(c.wait(CELL.replace("{pid}", pid), 10))
        c.js(MAIN_BTN if role == "tab" else STRIP.replace("{pid}", pid))
        c.wait(f"!{CELL.replace('{pid}', pid)}", 10)
    return out


def section(c, url: str, name: str) -> dict:
    c.go("about:blank")
    c.go(url)
    c.wait(f"!!document.querySelector('{READY[name]}')", 40)
    got = settled(c)
    shot(c, name)
    got["panels"] = each_panel(c, got.get("ids") or [])
    return {name: got}


def attention(c, url: str) -> dict:
    """3.3.16.0 R2: Live with the Attention queue open (the chip) and the inspector's glance."""
    c.go("about:blank")
    c.go(url)
    c.wait("!!document.querySelector('[data-testid=agents-attention]') && !!document.querySelector('[data-testid=roles-live-map]')", 40)
    c.js("document.querySelector('[data-testid=agents-attention]').click(); 1")
    c.wait("!!document.querySelector('[data-panel=fleet-attention] .panel-body')", 10)
    c.js("document.querySelector('.section-view:not([hidden]) [data-testid=viewbar-btn][data-panel=roles-inspector]')?.click(); 1")
    c.wait("!!document.querySelector('[data-testid=live-glance-lines]')", 20)  # the glance's lines
    got = settled(c)
    shot(c, "agents-attention")
    return {"agents-attention": got}


def living(c, url: str) -> dict:
    """3.3.18.0 "The living canvas": Live's History drawer open over the seeded home (its head a bar, its rows targets;
    the one sentence and a block's bar are measured where agents run: tests/helpers/studio_live_plan.py)."""
    q = lambda t: f"document.querySelector('[data-testid=\"{t}\"]')"  # noqa: E731
    c.js("try { localStorage.removeItem('halo.studio.layout.roles'); } catch (e) {} 1")  # the sections above moved its panels
    c.go("about:blank")
    c.go(url)
    c.wait(f"!!{q('live-history')} && !!{q('roles-live-empty')}", 40)
    drawn = f"!!{q('live-history-head')} && (!!{q('live-history-row')} || !!{q('live-history-none')})"
    for _ in range(2):  # a click that landed while the page still laid out is pressed once more
        c.js(f"{q('live-history-drawer')} || {q('live-history')}.click(); 1")
        try:
            c.wait(drawn, 20)
            break
        except TimeoutError:
            pass
    c.wait(drawn, 20)
    out = {"agents-live-history": settled(c)}
    shot(c, "agents-live-history")
    return out


def page_url(srv, mode: str, extra: str = "") -> str:
    from halo_harness.studio.server import url_for
    return url_for(srv, mode).replace(f"?mode={mode}", f"?mode={mode}{extra}&tour=off")


def inspector(c, srv) -> dict:
    """Cast with the halo-dev-cycle lineup open: the inspector's summary, then the Budget page."""
    from halo_harness.studio.server import url_for
    q = lambda t: f"document.querySelector('[data-testid=\"{t}\"]')"  # noqa: E731
    c.go("about:blank")
    c.go(url_for(srv, None, "lineup:halo-dev-cycle").replace("#t=", "&tour=off#t="))
    c.wait(f"!!{q('roles-summary')}", 40)
    out = {"inspector-summary": settled(c)}
    shot(c, "inspector-summary")
    c.js(f"{q('roles-edit-budget')}.click(); 1")
    c.wait(f"!!{q('roles-page-budget')}", 10)
    out["inspector-page"] = settled(c)
    shot(c, "inspector-page")
    return out


class DensityDriver(Driver):
    no_chrome = {"skip": "no Chrome found"}
    width, height = 1440, 900

    @contextmanager
    def session(self, c):
        from capture_studio import seeded_home
        from halo_harness.studio.server import start_server
        from tests.helpers.prompt_rig import PromptRig
        SHOTS[:] = self.argv[:1]
        state = seeded_home()
        proj = state.parent / "project"
        proj.mkdir(exist_ok=True)
        srv = start_server(port=0, cwd=proj, state_dir=state)
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        try:
            with PromptRig() as rig:  # Session and Live on the fleet over a live session (the Prompt rig); the rest over the seeded home
                live = (("session", rig.url(f"&session={rig.sid}")), ("agents-busy", page_url(rig.server, "agents", "&view=live")))
                seeded = tuple((n, page_url(srv, m, x)) for n, m, x in SECTIONS if n not in ("session", "agents-busy"))
                yield tuple((section, (c, u, n)) for n, u in live + seeded) + ((inspector, (c, srv)), (attention, (c, page_url(rig.server, "agents", "&view=live"))),
                    (living, (c, page_url(srv, "agents", "&view=live"))))
        finally:
            srv.shutdown()
            srv.server_close()
            shutil.rmtree(state.parent, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(DensityDriver(sys.argv[1:]).main())
