"""tests.helpers.studio_run_parts -- what the 3.6.0.0 lit Map showed of a run, back on BOTH run drawings (Halo 3.6.0.2, P4
batch 13: Session's Live drawer and Agents -> 4 · Live, one set of parts, routes/crew/map/runParts.tsx), in headless
Chrome over tests/helpers/studio_session_rig.py and tests/helpers/studio_live_rig.py: the session runs on `shop`
(tests/helpers/studio_map_live.py), five helpers made up under main. No model is called. For each drawing (`session`,
`live`) every step is recorded on its own (`{where}.{step}.error` when it raised), so one missing part never hides another:

    clock    a helper in a Bash call: its row says the tool and its seconds, which grow (waited for, up to 15 s) while
             every box of the drawing keeps its rect (0.5 px)
    talk     main talks to the implementer (box code): the line main -> code pulses (`data-talk`), and no other line
    jk       the focus in the drawing: J picks the first box in drawing order, J the next, K back; with the card's Steer
             field focused, J is typed and the selection stays
    timers   every `setInterval` of the page is recorded from its boot: the intervals born while the drawing was shown
             (at least one: its clock) are all cleared once it is hidden (Session: Agents opened; Live: 3 · Map)
    under    main's box draws three of its rows and says "+{n} under it" for the rest; a press opens 4 · Live's Feed on
             main's `under:` page
    wait     (batch 13's repair) main hands work to the implementer, which is in a Bash call: the box holding it (code)
             carries the 3.6.0.0 outline (`data-waited`), the drawing's wait link says "waiting on: ... -> Bash ..." and
             a press picks that box (selected, its card open)
    waited   a drawn helper asks and waits on him: its row says "waiting for you · {n} s", the seconds grow, no box moves
    below    (P7, Session only) at 1280 x 800, before and while the wait link shows: "↓ n more below" keeps its rect and
             one line, the slot its 32 px, the wait link sits inside the slot with its words whole

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
    s0, s1, moved = ticks(c, where, row)
    return {"tool": c.js(f"{row}.querySelector('[data-testid=run-clock]').dataset.tool"), "reads": [s0, s1], "moved": moved}


def until(c, expr: str, want, timeout: float = 10):
    """`expr`'s value once it equals `want` (waited for, so a slow runner only waits longer), else its last value."""
    import json
    try:
        c.wait(f"JSON.stringify({expr}) === {json.dumps(json.dumps(want, separators=(',', ':')))}", timeout)
    except Exception:
        pass
    return c.js(expr)


def ticks(c, where: str, row: str) -> tuple:
    """The row's clock read, then read again once its seconds have grown (waited for, up to 15 s: no wall-clock margin),
    and the boxes of the drawing whose rect moved between the two reads (0.5 px)."""
    text = f"{row}.querySelector('[data-testid=run-clock]').textContent"
    secs = f"(+(({text}).match(/· (\\d+) s$/) || [0, -1])[1])"
    r0, s0 = c.js(rects(where)), c.js(text)
    n0 = c.js(secs)
    try:
        c.wait(f"{secs} > {n0}", 15)
    except Exception:
        pass
    r1, s1 = c.js(rects(where)), c.js(text)
    return s0, s1, sorted(k for k in r0 if k in r1 and max(abs(a - b) for a, b in zip(r0[k], r1[k])) > 0.5)


def wait_link(c, lv, where: str) -> dict:
    """main hands work to the implementer (an `Agent` call) which is in a Bash call: the session waits on the implementer,
    so the box holding it (code) is outlined, and the drawing's wait link names it; a press picks that box."""
    outlined = f"{boxes(where)}.filter((b) => b.hasAttribute('data-waited')).map((b) => b.dataset.box)"
    link = f"document.querySelector('{ROOT[where]} [data-testid=run-wait]')"
    row = f"Math.round(document.querySelector('{ROOT[where]} [data-testid=run-wait-row]')?.getBoundingClientRect().height ?? -1)"
    out: dict = {"helper": lv.aid("implementer"), "row_before": c.js(row)}
    try:
        lv.tool("main", "Agent", f"call-{where}-agent")
        # P8: a long tool line -- the link shows its words whole on its reserved row, which keeps its height
        lv.tool("implementer", "Bash", f"call-{where}-bash", current="pytest -q tests/test_a_rather_long_module_name_for_the_slot.py")
        out["outlined"] = until(c, outlined, ["code"])
        c.wait(f"{link}?.textContent", 10)
        out.update({"link": c.js(f"{link}.textContent"), "leaf": c.js(f"{link}.dataset.leaf"), "row_after": c.js(row),
                    "whole": c.js(WHOLE.replace("$LINK", link))})
        c.js(f"{link}.click(); 1")
        out["picked"] = until(c, f"[({q(where, '> [data-selected]')}?.dataset.box || ''), !!document.querySelector('{ROOT[where]} [data-testid=map-step-in]')]", ["code", True])
    finally:
        lv.result("main", f"call-{where}-agent", "done", tool="Agent")
        lv.result("implementer", f"call-{where}-bash", "ok")
        lv.state("implementer", current="thinking")
    return out


# P8: an element's words whole: nothing overflows it and no ellipsis, nowrap or line clamp is on it or its row
WHOLE = """(() => { const e = $LINK; if (!e) return null; const cut = (x) => { const s = getComputedStyle(x);
  return s.textOverflow === 'ellipsis' || s.whiteSpace === 'nowrap' || s.webkitLineClamp !== 'none'; };
  return e.scrollWidth <= e.clientWidth + 1 && e.scrollHeight <= e.clientHeight + 1 && ![e, ...e.querySelectorAll('*'), e.parentElement].some(cut); })()"""


# P7: Session's bottom slot -- "↓ n more below" (its rect, how many lines its words take), the slot's height and width, and
# whether the wait link (when shown) lies inside the slot with its words whole
BELOW = """(() => { const s = document.querySelector('[data-testid=session-map-below]'); if (!s) return null;
  const m = s.querySelector('[data-testid=map-more-below]'), w = s.querySelector('[data-testid=run-wait]'), S = s.getBoundingClientRect();
  const lines = (el) => { const g = document.createRange(); g.selectNodeContents(el); return new Set([...g.getClientRects()].filter((x) => x.width > 0).map((x) => Math.round(x.top))).size; };
  const r = m && m.getBoundingClientRect(), W = w && w.getBoundingClientRect(), t = w && (w.querySelector('.mp-wait-words') || w);
  let nat = 0; if (m) { const k = m.cloneNode(true); k.style.cssText = 'position:absolute;visibility:hidden;white-space:nowrap;'; s.appendChild(k); nat = k.getBoundingClientRect().width; k.remove(); }
  return { more: r ? [r.left, r.top, r.width, r.height].map(Math.round) : null, lines: m ? lines(m) : 0, natural: !!r && Math.abs(r.width - nat) < 0.5,
    slot: [Math.round(S.width), Math.round(S.height)], wait: !!w,
    inside: !W || (W.top >= S.top - 0.5 && W.bottom <= S.bottom + 0.5 && W.left >= S.left - 0.5 && W.right <= S.right + 0.5),
    whole: !w || (w.scrollWidth <= w.clientWidth + 1 && w.scrollHeight <= w.clientHeight + 1
      && ![w, t].some((x) => { const c = getComputedStyle(x); return c.textOverflow === 'ellipsis' || c.whiteSpace === 'nowrap' || c.webkitLineClamp !== 'none'; })) }; })()"""


def settled(c, expr: str, tries: int = 12):
    """`expr`'s value once two reads 300 ms apart are alike (the drawing re-fitted after a resize), else its last value."""
    last = c.js(expr)
    for _ in range(tries):
        time.sleep(0.3)
        now = c.js(expr)
        if now == last:
            return now
        last = now
    return last


def below(c, lv, where: str) -> dict:
    """At 1280 x 800, before and while a long wait link shows: "↓ n more below" keeps its rect, its own (natural) width and
    one line; the slot keeps its height (P8: "more below"'s 32 px row and the wait link's reserved row); the wait link lies
    inside the slot, its words whole."""
    out: dict = {}
    c.call("Emulation.setDeviceMetricsOverride", width=1280, height=800, deviceScaleFactor=1, mobile=False)
    try:
        # the drawer at its least width: its splitter dragged as far in as it goes (the drawer stops at its least width)
        sp = c.js("""(() => { const d = document.querySelector('[data-testid=session-map-below]')?.closest('[data-testid=stage-drawer]');
          const s = d?.querySelector(':scope > [data-testid=stage-splitter]'); if (!s) return null; const r = s.getBoundingClientRect();
          return [r.left + r.width / 2, r.top + r.height / 2, d.dataset.side]; })()""")
        if sp:
            c.drag(sp[0], sp[1], sp[0] + (-600 if sp[2] == "left" else 600), sp[1])
            c.mouse("mouseMoved", 2, 790)
        out["drawer"] = settled(c, "Math.round(document.querySelector('[data-testid=session-map-below]')?.closest('[data-testid=stage-drawer]')?.getBoundingClientRect().width || 0)")
        out["before"] = settled(c, BELOW)
        lv.tool("main", "Agent", "call-below-agent")
        lv.tool("implementer", "Bash", "call-below-bash", current="pytest -q tests/test_a_rather_long_module_name_for_the_slot.py")
        link = "document.querySelector('[data-testid=session-map-below] [data-testid=run-wait]')?.textContent"
        try:
            c.wait(f"{link}?.includes('rather_long')", 15)
        except TimeoutError:
            out["link"] = c.js(f"{link} || null")
        out["after"] = settled(c, BELOW)
    finally:
        lv.result("main", "call-below-agent", "done", tool="Agent")
        lv.result("implementer", "call-below-bash", "ok")
        lv.state("implementer", current="thinking")
        c.call("Emulation.setDeviceMetricsOverride", width=1500, height=900, deviceScaleFactor=1, mobile=False)
    return out


def waited(c, lv, where: str) -> dict:
    """A drawn helper asks and waits on him: its row says what it waits for and for how long, and the seconds grow while
    no box moves."""
    mine = [h[0] for h in HELPERS]
    shown = c.js(f"[...{q(where, '[data-box=main]')}.querySelectorAll('[data-row]:not([hidden])')].map((r) => r.dataset.row)")
    aid = next(a for a in shown if a in mine)
    name = lv.rows[aid]["name"]
    row = q(where, f"[data-row={aid}]")
    try:
        lv.state(name, state="waiting")
        lv.ask(name)
        c.wait(f"{row}?.querySelector('[data-testid=run-clock-secs]')?.textContent", 10)
        s0, s1, moved = ticks(c, where, row)
        return {"reads": [s0, s1], "moved": moved, "kind": c.js(f"{row}.querySelector('[data-testid=run-clock]').dataset.wait || ''")}
    finally:
        lv.state(name, state="running")


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
    for ch, want in zip(("j", "j", "k"), (order[0], order[1], order[0])):
        key(c, ch)
        got.append(until(c, sel, want, 10))  # waited for: a slow runner only waits longer
    field = f"document.querySelector('{ROOT[where]} [data-testid=map-step-in] textarea, {ROOT[where]} [data-testid=map-step-in] input')"
    has = c.js(f"!!{field}")
    if has:
        c.js(f"{field}.focus(); 1")
        key(c, "j")
        try:
            c.wait(f"{field}.value.includes('j')", 10)  # the key landed in the field; the selection is read after it
        except Exception:
            pass
        time.sleep(1.0)
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
                     ("under", lambda: (open_where(c, rig, lv, where), under(c, where))[1]),
                     ("wait", lambda: (open_where(c, rig, lv, where), wait_link(c, lv, where))[1]),
                     ("below", lambda: (open_where(c, rig, lv, where), below(c, lv, where))[1]),
                     ("waited", lambda: (open_where(c, rig, lv, where), waited(c, lv, where))[1])):
        if name == "below" and where != "session":
            continue  # the bottom slot is Session's drawer's
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
