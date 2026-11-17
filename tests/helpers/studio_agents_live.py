"""tests.helpers.studio_agents_live -- Agents -> 4 · Live (Halo 3.6.0.2 R52), in headless Chrome as a first-time user,
over tests/helpers/studio_session_rig.py (this harness's real session: main, an implementer and a researcher mid-work)
and tests/helpers/studio_live_rig.py (the session row's `map` and `map_next`, as tests/helpers/studio_map_live.py uses
them). No model is called.

    doors     the old `?mode=agents&view=live` door opens Live (its tab pressed); the four tabs' words; the Live part
              holds the shell (the T-state line, the status line, the frame) in its own workspace `agents-live`; the
              dot on 4 · Live while a session runs, not on 3 · Map; keys C -> Map, L -> Live, 3 -> Map, 4 -> Live; Live
              remembered as the tab used last; the palette's `Agents: 4 · Live` line, its key, Enter lands on Live
    opens     R56 (decision 4): the rig's session between turns (a turn had, every agent done, not busy), the tab used
              last 1 · Agents: Alt+2 from Session opens Agents on 4 · Live; `?` there says the opening rule; Alt+1 back to
              Session. Then the session as a Studio-started one with no message yet (T10), the tab used last 2 · Workflows:
              Alt+2 opens on Workflows
    boots     the coordinator's ruling on R56: a page loaded on Agents with no `view=` (the session between turns, the tab
              used last 1 · Agents) shows "Reading the sessions." and no view, then opens on Live, no other view drawn
              first (a recorder installed before the app boots); with only a T10 session open it opens on the tab used
              last (2 · Workflows), again no other view first
    never_flips  R56: the session between turns; a recorder of `[data-testid=agents]`'s `data-view` from its first draw;
              Alt+2, then busy, idle, busy (three `sessions` frames, each read by the page); 2 s more: one value, `live`
    follows, holds, t9   R34 R12 R3: the drawing (tests/helpers/studio_agents_live_draw.py: the map `shop` is seeded in
              the rig's home; the reviewer is the workflow review's step, in the box `check`)
    feed      R57: the Feed is Live's right drawer, the Map keeps Run a goal and History in its own (tests/helpers/
              studio_live_feed.py `feed_step`)
    quiet, picker, receipt, away, waits, reread   R24 R33 R55: 3 · Map is the plan (tests/helpers/studio_map_quiet.py)

    python -m tests.helpers.studio_agents_live
"""
from __future__ import annotations

import sys
from contextlib import contextmanager
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from tests.helpers.chrome_driver import Driver  # noqa: E402
from tests.helpers.studio_agents import key  # noqa: E402

VIEW = "document.querySelector('[data-testid=agents]')?.dataset.view"
P = "[data-part=live]"


def q(sel: str) -> str:
    return f"document.querySelector('{sel}')"


def doors(c, rig, lv) -> dict:
    out: dict = {}
    c.go(rig.url("agents", "&view=live"))
    out["door"] = c.wait(f"{VIEW} === 'live' && {VIEW}", 40)
    tab = q(f"{P} [data-testid=agents-view-live]")
    out["pressed"] = c.wait(f"{tab}?.getAttribute('aria-pressed')", 20)
    out["switch"] = c.js(f"[...document.querySelectorAll('{P} [data-testid=agents-views] button')].map((b) => b.textContent)")
    out["shown"] = c.js(f"!{q(P)}.hidden && !!{q(P + ' [data-testid=agents-live]')}")
    out["workspace"] = c.js(f"{q(P + ' .workspace')}?.dataset.section || ''")
    truth = q(f"{P} [data-testid=live-truth]")
    out["truth"] = c.wait(f"{truth}?.dataset.state === 'T1' && [{truth}.dataset.state, {truth}.textContent]", 30)
    out["status"] = c.js(f"!!{q(P + ' [data-testid=live-status]')}")
    out["frame"] = c.js(f"!!{q(P + ' [data-testid=live-frame]')}")
    lv.refresh(busy=True)
    out["dot"] = c.wait(f"{tab}?.dataset.running === '1' && [{tab}.dataset.running, {tab}.textContent]", 30)
    out["map_dot"] = c.js(f"{q(P + ' [data-testid=agents-view-map]')}?.dataset.running || ''")
    c.js("document.activeElement?.blur(); 1")
    for ch, want in (("c", "map"), ("l", "live"), ("3", "map"), ("4", "live")):
        key(c, ch)
        out[f"key_{ch}"] = c.wait(f"{VIEW} === '{want}' && {VIEW}", 20)
    out["remembered"] = c.js("(() => { try { return localStorage.getItem('halo.studio.agents-view'); } catch { return 'unreadable'; } })()")
    key(c, "3")
    c.wait(f"{VIEW} === 'map'", 20)
    c.click_on(q(".palette-btn"))
    c.wait("document.activeElement?.classList.contains('palette-input')", 10)
    c.type_text("Agents: 4")
    rows = "[...document.querySelectorAll('[data-testid=palette] .palette-item')]"
    out["palette"] = c.wait(f"(() => {{ const r = {rows}.filter((x) => x.querySelector('.palette-label').textContent.startsWith('Agents: 4'));"
                            f" return r.length && r.map((x) => [x.querySelector('.palette-label').textContent,"
                            f" (x.querySelector('kbd')?.textContent || '').trim()]); }})()", 15)
    out["palette_first"] = c.js(f"{rows}[0]?.querySelector('.palette-label').textContent || ''")
    c.key("Enter")
    out["palette_to"] = c.wait(f"!document.querySelector('[data-testid=palette]') && {VIEW}", 15)
    return out


LINE = q("[data-testid=session-lit-line]")  # Session's T-state line: the page has read the rig's row
READS = r"performance.getEntriesByType('resource').filter((e) => /\/api\/live(\?|$)/.test(e.name)).length"
TAB = "(document.querySelector('[data-testid=\"section-tab\"][aria-selected=\"true\"]')?.textContent || '')"


def fresh(c, rig, last: str) -> None:
    """Session in a new page, with `last` as the tab used last (the rig's page is the only origin that can write it).
    Each load starts from about:blank: the same URL again would be a hash change, not a new page."""
    for i in range(2):
        c.go("about:blank")
        c.wait("location.href === 'about:blank'", 10)
        c.go(rig.url("session"))
        if not i:
            c.wait(f"!!{LINE}", 40)
            c.js(f"localStorage.setItem('halo.studio.agents-view', '{last}'); 1")


def alt(c, n: int) -> None:
    c.js("document.activeElement?.blur(); 1")
    key(c, str(n), alt=True)


def opens(c, rig, lv, rows) -> dict:
    out: dict = {}
    rows.idle(lv.sid, turns=1, parent=None, asked=False)  # between turns: a turn had, every agent done, not busy
    fresh(c, rig, "crew")
    c.wait(f"{LINE}?.dataset.state && {LINE}.dataset.state !== 'T10'", 40)
    alt(c, 2)
    out["opens"] = c.wait(VIEW, 20)
    out["alt2"] = c.wait(f"{TAB}.startsWith('Agents') && {TAB}", 10)
    c.js("document.activeElement?.blur(); 1")
    key(c, "?")
    out["help"] = c.wait("document.querySelector('[data-testid=section-help]')?.textContent", 10)
    c.click_on(q("[data-testid=section-help-ok]"))
    c.wait("!document.querySelector('[data-testid=section-help]')", 10)
    alt(c, 1)
    out["alt1"] = c.wait(f"{TAB}.startsWith('Session') && {TAB}", 10)
    rows.idle(lv.sid, parent="studio:1", turns=0, asked=False)  # T10: Studio-started, no message yet; no other session
    fresh(c, rig, "workflows")
    c.wait(f"{LINE}?.dataset.state === 'T10'", 40)
    alt(c, 2)
    out["t10"] = c.wait(VIEW, 20)
    return out


def never_flips(c, rig, lv, rows) -> dict:
    out: dict = {}
    rows.reset()
    rows.idle(lv.sid, turns=1, parent=None, asked=False)
    fresh(c, rig, "crew")
    c.wait(f"{LINE}?.dataset.state && {LINE}.dataset.state !== 'T10'", 40)
    c.js("""(() => { window.__views = [];
      const rec = () => { const v = document.querySelector('[data-testid=agents]')?.dataset.view;
        if (v && v !== window.__views[window.__views.length - 1]) window.__views.push(v); };
      new MutationObserver(rec).observe(document.body, { subtree: true, childList: true, attributes: true, attributeFilter: ['data-view'] });
      return 1; })()""")
    alt(c, 2)
    c.wait("window.__views.length > 0", 20)
    n0 = n = c.js(READS)
    for step in (lambda: rows.turn(lv.sid, turns=1), lambda: rows.idle(lv.sid, turns=1), lambda: rows.turn(lv.sid, turns=1)):
        step()  # each frame read by the page before the next: the three states each reach it
        c.wait(f"{READS} > {n}", 20)
        n = c.js(READS)
    out["flip_reads"] = n - n0  # GET live re-read after each frame
    try:  # bounded: any second value recorded within 2 s more is a flip
        c.wait("window.__views.length > 1", 2)
    except TimeoutError:
        pass
    out["flips"] = c.js("window.__views")
    return out


RECORD = """(() => { window.__drawn = []; window.__reading = false;
  const rec = () => { if (document.querySelector('[data-testid=agents-reading-line]')) window.__reading = true;
    for (const p of document.querySelectorAll('.ag-part[data-part]'))
      if (!window.__drawn.includes(p.dataset.part)) window.__drawn.push(p.dataset.part); };
  new MutationObserver(rec).observe(document, { subtree: true, childList: true, attributes: true }); })();"""


def boots(c, rig, lv, rows) -> dict:
    out: dict = {}
    c.call("Page.enable")
    ident = c.call("Page.addScriptToEvaluateOnNewDocument", source=RECORD)["identifier"]
    try:
        for name, last, row in (("talked", "crew", dict(turns=1, parent=None, asked=False)),
                                ("t10", "workflows", dict(turns=0, parent="studio:1", asked=False))):
            rows.reset()
            rows.idle(lv.sid, **row)
            fresh(c, rig, last)
            c.go("about:blank")
            c.wait("location.href === 'about:blank'", 10)
            c.go(rig.url("agents"))  # a page load on Agents, no view in the address
            out[name] = c.wait(f"!document.querySelector('[data-testid=agents-reading]') && {VIEW}", 40)
            out[f"{name}_drawn"] = c.js("window.__drawn")
            out[f"{name}_reading"] = c.js("window.__reading")
    finally:
        c.call("Page.removeScriptToEvaluateOnNewDocument", identifier=ident)
    return out


class AgentsLiveDriver(Driver):
    no_chrome = {"skip": "no Chrome found"}
    width, height = 1500, 900

    @contextmanager
    def session(self, c):
        from tests.helpers.studio_live_rig import Live
        from tests.helpers.studio_session_rig import StudioSessionRig
        from tests.helpers import studio_agents_live_draw as D
        from tests.helpers.studio_map_live import MAP
        from tests.helpers.studio_live_feed import feed_step
        from tests.helpers.studio_map_quiet import STEPS as QUIET
        with StudioSessionRig() as rig:
            from halo_harness.crew import store
            store.write_text(store.path_for("map", "shop", state_dir=rig.state), MAP)  # the map the session's row names
            lv = Live(rig)
            lv.rows["r3v1e2w0"]["square"] = {"name": "review", "engine": "steps"}  # the workflow review's step: box check
            lv.refresh(map="shop", map_next="shop")
            from tests.helpers.studio_session_map_down import Rows
            rows = Rows(rig)  # over GET live's rows: the session's turns, parent, busy and its agents' states (R56)
            try:
                yield ((doors, (c, rig, lv)), (opens, (c, rig, lv, rows)), (boots, (c, rig, lv, rows)), (never_flips, (c, rig, lv, rows)),
                       (D.follows, (c, rig, lv, rows)), (D.holds, (c, rig, lv, rows)), (D.t9, (c, rig, lv, rows)), (feed_step, (c, rig, lv, rows)),
                       *((step, (c, rig, lv, rows)) for step in QUIET))
            finally:
                lv.close()


if __name__ == "__main__":
    sys.exit(AgentsLiveDriver(sys.argv[1:]).main())
