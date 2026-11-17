"""tests.helpers.studio_run_parts -- what the 3.6.0.0 lit Map showed of a run, back on BOTH run drawings (Halo 3.6.0.2, P4
batch 13: Session's Live drawer and Agents -> 4 · Live, one set of parts, routes/crew/map/runParts.tsx), in headless
Chrome over tests/helpers/studio_session_rig.py and tests/helpers/studio_live_rig.py: the session runs on `shop`
(tests/helpers/studio_map_live.py), five helpers made up under main. No model is called. For each drawing (`session`,
`live`) every step is recorded on its own (`{where}.{step}.error` when it raised), so one missing part never hides another:

    clock    a helper in a Bash call: its row says the tool and its seconds, which grow between two reads 1.2 s apart
             while every box of the drawing keeps its rect (0.5 px)
    talk     main talks to the implementer (box code): the line main -> code pulses (`data-talk`), and no other line
    jk       the focus in the drawing: J picks the first box in drawing order, J the next, K back; with the card's Steer
             field focused, J is typed and the selection stays
    timers   every `setInterval` of the page is recorded from its boot: the intervals born while the drawing was shown
             (at least one: its clock) are all cleared once it is hidden (Session: Agents opened; Live: 3 · Map)
    under    main's box draws three of its rows and says "+{n} under it" for the rest; a press opens 4 · Live's Feed on
             main's `under:` page

    python -m tests.helpers.studio_run_parts
"""
from __future__ import annotations

import sys
import time
from contextlib import contextmanager
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from tests.helpers.chrome_driver import Driver  # noqa: E402
from tests.helpers.studio_agents import key  # noqa: E402

ROOT = {"session": "[data-testid=session-lit-map]", "live": "[data-part=live] [data-testid=live-frame]"}
WORLD = {"session": ".mp-mini-world", "live": "[data-testid=live-world]"}
SCROLL = {"session": ".mp-mini-scroll", "live": "[data-testid=live-scroll]"}
VIEW = "document.querySelector('[data-testid=agents]')?.dataset.view"
HELPERS = [(f"h3lp3r0{i}", f"helper-{i}", f"Count the tests of suite {i}") for i in range(1, 6)]
IV = """(() => { const live = new Map(); window.__iv = live; const si = window.setInterval, ci = window.clearInterval;
  window.setInterval = function (fn, ms, ...r) { const id = si.call(window, fn, ms, ...r); live.set(id, [Number(ms) || 0, performance.now()]); return id; };
  window.clearInterval = function (id) { live.delete(id); return ci.call(window, id); }; })();"""


def q(where: str, sel: str = "") -> str:
    return f"document.querySelector('{ROOT[where]} {WORLD[where]}{(' ' + sel) if sel else ''}')"


def boxes(where: str) -> str:
    return f"[...document.querySelectorAll('{ROOT[where]} {WORLD[where]} > [data-box]')]"


def rects(where: str) -> str:
    return f"Object.fromEntries({boxes(where)}.map((b) => {{ const r = b.getBoundingClientRect(); return [b.dataset.box, [r.left, r.top, r.width, r.height]]; }}))"


def open_where(c, rig, lv, where: str) -> None:
    from tests.helpers.studio_session import boot_go, url
    lv.refresh(map="shop", map_next="shop", busy=True)
    boot_go(c, url(rig, f"mode=session&session={lv.sid}&open=session-map") if where == "session" else rig.url("agents", "&view=live"))
    c.wait(f"{boxes(where)}.length >= 5 && !!{q(where, '[data-box=main] [data-row]')}", 40)
    c.mouse("mouseMoved", 2, 890)  # the pointer off the drawing (R12 holds it still under the pointer)


def clock(c, lv, where: str, n: int) -> dict:
    mine = [h[0] for h in HELPERS]
    shown = c.js(f"[...{q(where, '[data-box=main]')}.querySelectorAll('[data-row]:not([hidden])')].map((r) => r.dataset.row)")
    aid = next(a for a in shown if a in mine)
    lv.tool(lv.rows[aid]["name"], "Bash", f"call-{where}-{n}")
    row = f"{q(where, f'[data-row={aid}]')}"
    c.wait(f"{row}?.querySelector('[data-testid=run-clock-secs]')?.textContent", 10)
    last = c.js(rects(where))
    for _ in range(12):  # the drawing settled after its first draw (two reads 500 ms apart alike); the tick is what is read
        time.sleep(0.5)
        now = c.js(rects(where))
        if now == last:
            break
        last = now
    r0, s0 = c.js(rects(where)), c.js(f"{row}.querySelector('[data-testid=run-clock]').textContent")
    time.sleep(1.2)
    r1, s1 = c.js(rects(where)), c.js(f"{row}.querySelector('[data-testid=run-clock]').textContent")
    moved = sorted(k for k in r0 if k in r1 and max(abs(a - b) for a, b in zip(r0[k], r1[k])) > 0.5)
    return {"tool": c.js(f"{row}.querySelector('[data-testid=run-clock]').dataset.tool"), "reads": [s0, s1], "moved": moved}


def talk(c, lv, where: str) -> dict:
    lit = f"[...document.querySelectorAll('{ROOT[where]} {WORLD[where]} .mp-line[data-talk]')].map((p) => [p.dataset.from, p.dataset.to])"
    before = c.js(lit)
    lv.talk("main", "implementer", "Use the new discount table before tax")
    return {"before": before, "lit": c.wait(f"{lit}.length && {lit}", 8)}


def jk(c, where: str) -> dict:
    sel = f"({q(where, '> [data-selected]')}?.dataset.box || '')"
    order = c.js(f"{boxes(where)}.map((b) => [b.dataset.box, b.getBoundingClientRect()]).sort((a, b) => "
                 + ("a[1].left - b[1].left || a[1].top - b[1].top" if where == "live" else "a[1].top - b[1].top || a[1].left - b[1].left")
                 + ").map((x) => x[0])")
    c.js(f"document.querySelector('{ROOT[where]} {SCROLL[where]}').focus(); 1")
    got = []
    for ch in ("j", "j", "k"):
        key(c, ch)
        time.sleep(0.3)
        got.append(c.js(sel))
    field = f"document.querySelector('{ROOT[where]} [data-testid=map-step-in] textarea, {ROOT[where]} [data-testid=map-step-in] input')"
    has = c.js(f"!!{field}")
    if has:
        c.js(f"{field}.focus(); 1")
        key(c, "j")
        time.sleep(0.3)
    return {"order": order[:3], "got": got, "field": has, "after_field": c.js(sel), "typed": c.js(f"{field}?.value || ''") if has else ""}


def timers(c, where: str) -> dict:
    from tests.helpers.studio_agents_live import alt
    if where == "session":
        c.js("document.querySelector('.ws-cell[data-panel=\"session-map\"] [data-testid=panel-collapse]').click(); 1")
        c.wait(f"!document.querySelector('{ROOT[where]}')", 10)
        t0 = c.js("performance.now()")
        c.js("document.querySelector('.section-view:not([hidden]) [data-testid=\"viewbar-btn\"][data-panel=\"session-map\"]').click(); 1")
    else:
        c.js("document.activeElement?.blur(); 1")
        key(c, "3")
        c.wait(f"{VIEW} === 'map'", 10)
        t0 = c.js("performance.now()")
        key(c, "4")
    c.wait(f"{VIEW if where == 'live' else 'true'} && !!{q(where, '[data-testid=run-clock-secs]')}", 20)
    time.sleep(1.5)  # the clock ticks while shown
    t1 = c.js("performance.now()")
    alive = f"[...window.__iv.values()].filter((v) => v[1] >= {t0} && v[1] <= {t1}).map((v) => v[0])"
    shown = c.js(alive)  # the intervals the drawing's showing started, alive while it is shown
    c.js("document.activeElement?.blur(); 1")
    if where == "session":
        alt(c, 2)
        c.wait("document.querySelector('[data-testid=\"section-tab\"][aria-selected=\"true\"]')?.textContent.startsWith('Agents')", 10)
    else:
        key(c, "3")
        c.wait(f"{VIEW} === 'map'", 10)
    time.sleep(1.5)
    return {"shown": shown, "left": c.js(alive)}


def under(c, where: str) -> dict:
    more = q(where, "[data-box=main] [data-testid=session-map-rows-more]")
    out = {"text": c.js(f"{more}?.textContent || ''"), "tag": c.js(f"{more}?.tagName || ''"),
           "hidden": c.js(f"{q(where, '[data-box=main]')}.querySelectorAll('[data-row][hidden]').length"), "of": c.js(f"{more}?.dataset.under || ''")}
    c.js(f"{more}.click(); 1")
    page = "document.querySelector('[data-part=live] [data-testid=map-feed-under]')"
    out["feed"] = c.wait(f"{VIEW} === 'live' && {page}?.dataset.of && [{VIEW}, {page}.dataset.of, "
                         "document.querySelector('[data-part=live] [data-testid=map-feed-filter]')?.value]", 15)
    return out


def drawing(c, rig, lv, where: str) -> dict:
    out: dict = {}
    for name, fn in (("clock", lambda: clock(c, lv, where, 1)), ("talk", lambda: talk(c, lv, where)), ("jk", lambda: jk(c, where)),
                     ("timers", lambda: (open_where(c, rig, lv, where), clock(c, lv, where, 2), timers(c, where))[2]),
                     ("under", lambda: (open_where(c, rig, lv, where), under(c, where))[1])):
        try:
            if name == "clock":
                open_where(c, rig, lv, where)
            out.update({f"{where}.{name}.{k}": v for k, v in fn().items()})
        except Exception as e:  # each part on its own: one missing never hides another
            out[f"{where}.{name}.error"] = f"{type(e).__name__}: {e}"[:300]
    return out


class RunPartsDriver(Driver):
    no_chrome = {"skip": "no Chrome found"}
    width, height = 1500, 900

    @contextmanager
    def session(self, c):
        from tests.helpers.studio_live_rig import Live
        from tests.helpers.studio_session_rig import StudioSessionRig
        from tests.helpers.studio_map_live import MAP
        with StudioSessionRig() as rig:
            from halo_harness.crew import store
            store.write_text(store.path_for("map", "shop", state_dir=rig.state), MAP)
            lv = Live(rig)
            for aid, name, task in HELPERS:
                lv.spawn(aid, name, "general-purpose", "or:mock/glm-5-coder", task)
                lv.rows[aid]["crew"] = {"map": "shop", "box": "main", "made_up": True}
            c.call("Page.enable")
            c.call("Page.addScriptToEvaluateOnNewDocument", source=IV)
            try:
                yield tuple((drawing, (c, rig, lv, w)) for w in ("session", "live") if not self.argv or w in self.argv)
            finally:
                lv.close()


if __name__ == "__main__":
    sys.exit(RunPartsDriver(sys.argv[1:]).main())
