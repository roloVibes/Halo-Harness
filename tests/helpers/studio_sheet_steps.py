"""tests.helpers.studio_sheet_steps -- Halo 3.6.0.14 OP1 rule O1-5: the box's sheet as a person sees it, in headless Chrome
over the rig of tests/helpers/studio_live_now_steps.py (this harness's real session A, its rows set through GET live, the
feed frames a real session sends published on Studio's own bridge; S3's twelve helpers in seven groups). No model is
called. Every name and figure is invented; every expected figure is read from the page by the test.

    place    a member clicked (the coder of group 2 in Agents -> Live at 1440 x 900, the first researcher of group 1 in
             Session's drawer at its narrowest): the sheet's rect and what it stands against (sheetPlace.ts: data-side,
             its box, the view, the frame), every box's rect before the click, at the open, after a tool change and
             after an ask, and the sheet's own parts (Pause, Stop, the steer box, the body, NOW) in those three frames;
             then the drawer again with no sheet (`alone`): the same pointer, tool change and ask
    closers  Agents -> Live: the sheet opened again before each of an outside click, Escape, its x and a wheel over the
             drawing, gone after each; with it open, a pointer-down on another member opens THAT member's sheet
    motion   reduce, then no preference: what the sheet carried at its start (recorded as it changed), on its first
             frame once placed, and when Escape folded it
    body     group 1 with fourteen more helpers (its body longer than its room): the body under a wheel, the head and the
             action row around it, and the words of Last said

    python -m tests.helpers.studio_sheet_steps [step ...]
The last stdout line is a JSON object of what it saw.
"""
from __future__ import annotations

import sys
import time
from contextlib import contextmanager
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "tools"))

from tests.helpers.studio_auto_groups_draw import LSCROLL, LW, P, RECT  # noqa: E402
from tests.helpers.studio_live_now_steps import GROUPS, LiveNowDriver, ask, feed, frames, go, narrow, put, s3_rows, to_live, wait_or  # noqa: E402
from tests.helpers.studio_session_map_down import Rows  # noqa: E402
from tests.helpers.studio_session_run import M  # noqa: E402
from tests.helpers.studio_session_step_in import SHEET_GEO  # noqa: E402

ROOTS = {"live": LW, "session": M}
SHEET = {"live": f"document.querySelector('{P} .mp-step-in')", "session": f"{M}?.querySelector('.mp-step-in')"}
# the sheet `k`'s parts: where it stands (SHEET_GEO), its head, action row, Pause, Stop, steer box, body, NOW, its asks,
# how far the body and the sheet are scrolled, and Last said's lines
PARTS = ("((k) => { if (!k) return null; const R = " + RECT + ", q = (t) => k.querySelector(`[data-testid=${t}]`), b = q('map-step-in-body');"
         " return { open: k.hasAttribute('data-open'), target: k.dataset.target || '', rect: R(k), geo: (" + SHEET_GEO + ")(k),"
         " head: R(k.querySelector('.mp-step-in-head')), actions: R(q('map-step-in-actions')), pause: R(q('map-step-in-pause')),"
         " pauseText: q('map-step-in-pause')?.textContent || '', stop: R(q('map-step-in-stop')), steer: R(q('fleet-steer')), body: R(b),"
         " now: R(q('map-step-in-now')), nowText: q('map-step-in-now')?.textContent || '', asks: k.querySelectorAll('[data-testid=map-step-in-ask]').length,"
         " top: k.scrollTop, bodyTop: b ? b.scrollTop : null, bodyRoom: b ? [b.scrollHeight, b.clientHeight] : null,"
         " said: [...k.querySelectorAll('[data-testid=map-step-in-said]')].map((s) => [...s.querySelectorAll(':scope > p')].map((p) => p.textContent)) }; })")
BOXES = ("((root) => { const R = " + RECT + "; return root ? Object.fromEntries([...root.querySelectorAll('[data-box], [data-member]')]"
         ".map((e, i) => [(e.dataset.member ? 'm:' + e.dataset.member : 'b:' + e.dataset.box) + '#' + i, R(e)])) : null; })")


def parts(c, view: str) -> dict:
    return c.js(f"({PARTS})({SHEET[view]})") or {}


def boxes(c, view: str) -> dict:
    return c.js(f"({BOXES})({ROOTS[view]})") or {}


def is_open(view: str) -> str:
    return f"!!{SHEET[view]}?.hasAttribute('data-open')"


def gone(view: str) -> str:
    return f"!{SHEET[view]}"


def now_in(view: str, start: str) -> str:
    return f"({SHEET[view]}?.querySelector('[data-testid=map-step-in-now]')?.textContent || '').startsWith('{start}')"


def _s3(c, rig, rows: Rows, a: str, b: str, t0: float, view: str, h: int = 900, **st) -> None:
    go(c, rig, rows, a, b, s3_rows(rows, a, t0, **st), h=h)
    c.wait(f"{M}.querySelectorAll('{GROUPS}').length === 7", 20)
    if view == "live":
        to_live(c, 7)
    frames(c, 6)


def open_on(c, view: str, expr: str) -> None:
    c.click_on(expr)
    c.wait(is_open(view), 30)
    frames(c, 2)


# ---- place: where it opens, and nothing else moves ----------------------------------------------------------------------
AIDS = {"live": "k1", "session": "r1"}  # one asking member per drawing: an agent's ask stays open on the server for the run


def own_now(view: str, aid: str, start: str) -> str:
    return f"({ROOTS[view]}?.querySelector('[data-member={aid}] > [data-testid=map-member-now]')?.textContent || '').startsWith('{start}')"


def _hold(c, rig, rows: Rows, a: str, b: str, view: str, n: int, sheet: bool) -> dict:
    """The member AIDS[view] clicked (its sheet open) or, with `sheet` False, only the pointer resting where that click
    leaves it (the drawing alone); then a tool change and an ask: every box's rect at each, and the sheet's parts."""
    out: dict = {}
    t0, aid = time.time() - 40, AIDS[view]
    _s3(c, rig, rows, a, b, t0, view)
    if view == "session":
        out["drawer"] = narrow(c)
    mem = f"{ROOTS[view]}.querySelector('[data-member={aid}]')"
    c.js(f"{mem}.scrollIntoView({{block: 'nearest', inline: 'nearest'}}); 1")
    frames(c, 6)
    out["before"] = boxes(c, view)
    if sheet:
        open_on(c, view, mem)
    else:
        x, y, w, h = c.rect(mem)
        c.mouse("mouseMoved", x + w / 2, y + h / 2)
        frames(c, 2)
    out["open"], out["at_open"] = parts(c, view), boxes(c, view)
    feed(rig, a, aid, "tool_use_start", {"id": f"t-{aid}-{n}", "name": "Grep"})
    wait_or(c, now_in(view, "Grep · ") if sheet else own_now(view, aid, "Grep · "), 15)
    frames(c, 2)
    out["tool"], out["at_tool"] = parts(c, view), boxes(c, view)
    feed(rig, a, aid, "tool_result", {"id": f"t-{aid}-{n}", "name": "Grep", "content": "ok", "is_error": False})
    ask(rig, a, aid, n)
    put(rows, a, s3_rows(rows, a, t0, **{aid: "waiting"}))
    n0 = out["open"].get("asks") or 0
    wait_or(c, f"{now_in(view, 'waiting for you · ')} && ({SHEET[view]}?.querySelectorAll('[data-testid=map-step-in-ask]').length || 0) > {n0}" if sheet
            else own_now(view, aid, "waiting for you · "), 15)
    frames(c, 2)
    out["ask"], out["at_ask"] = parts(c, view), boxes(c, view)
    return out


def place(c, rig, rows: Rows, a: str, b: str) -> dict:
    out: dict = {}
    for view in ("live", "session"):
        out[view] = {**_hold(c, rig, rows, a, b, view, 1, True), "aid": AIDS[view]}
    # the drawer at its narrowest, no sheet: what the same tool change and ask move in the drawing itself (3.6.0.13: a
    # group's head counts may take a second row there); the sheet must move nothing beyond it
    out["session"]["alone"] = _hold(c, rig, rows, a, b, "session", 2, False)
    return {"place": out}


# ---- closers: what folds it ------------------------------------------------------------------------------------------------
# a point of the drawing that is no box, no line, no label, no link and not the sheet (read from the page)
EMPTY = f"""(() => {{ const s = {LSCROLL}, v = s.getBoundingClientRect();
  for (let y = v.top + 12; y < v.top + s.clientHeight - 12; y += 16) for (let x = v.left + 12; x < v.left + s.clientWidth - 12; x += 16) {{
    const e = document.elementFromPoint(x, y);
    if (e && s.contains(e) && !e.closest('[data-box], [data-member], .mp-label, .mp-hit, .mp-step-in, a, button, path, [data-testid=live-more-below]')) return [x, y]; }}
  return null; }})()"""
# another member whose middle a pointer reaches (not under the sheet)
OTHER = f"""(() => {{ for (const m of {LW}.querySelectorAll('[data-member]')) {{ if (m.dataset.member === 'k1') continue;
  const r = m.getBoundingClientRect(), e = r.height ? document.elementFromPoint(r.left + r.width / 2, r.top + r.height / 2) : null;
  if (e && m.contains(e)) return m.dataset.member; }} return null; }})()"""


def closers(c, rig, rows: Rows, a: str, b: str) -> dict:
    out: dict = {}
    t0 = time.time() - 40
    _s3(c, rig, rows, a, b, t0, "live")
    mem = f"{LW}.querySelector('[data-member=k1]')"
    for how in ("outside", "escape", "x", "wheel"):
        open_on(c, "live", mem)
        got: dict = {"opened": c.js(is_open("live"))}
        if how == "outside" or how == "wheel":
            pt = c.js(EMPTY)
            got["at"] = pt
            if pt and how == "outside":
                c.click(pt[0], pt[1])
            elif pt:
                c.mouse("mouseMoved", pt[0], pt[1])
                c.call("Input.dispatchMouseEvent", type="mouseWheel", x=pt[0], y=pt[1], deltaX=0, deltaY=40)
        elif how == "escape":
            c.js("document.activeElement?.blur?.(); 1")  # the key on the page, not in a field
            c.key("Escape")
        else:
            c.click_on(f"{SHEET['live']}.querySelector('[data-testid=map-step-in-close]')")
        got["gone"] = bool(wait_or(c, gone("live"), 20))
        out[how] = got
        c.mouse("mouseMoved", 2, 400)
    open_on(c, "live", mem)
    other = c.js(OTHER)
    got = {"other": other, "first": c.js(f"{SHEET['live']}?.dataset.target || ''")}
    if other:
        c.click_on(f"{LW}.querySelector('[data-member={other}]')")
        wait_or(c, f"{SHEET['live']}?.dataset.target === 'member:{other}' && {is_open('live')}", 15)
        got["then"] = c.js(f"{SHEET['live']}?.dataset.target || ''")
        got["open"] = c.js(is_open("live"))
        got["sheets"] = c.js(f"document.querySelectorAll('{P} .mp-step-in').length")
    out["pick"] = got
    return {"closers": out}


# ---- motion: reduce, then no preference ----------------------------------------------------------------------------------
# every attribute the sheet gained (recorded as it changed: data-unfold is set and taken off in one task), and its first
# frame once placed: usable? its own animations?
WATCH = """(() => { const log = window.__sheet = { adds: [], first: null };
  const mo = new MutationObserver((rs) => { for (const r of rs) { const el = r.target;
    if (!(el instanceof Element) || !el.classList.contains('mp-step-in')) continue;
    if (r.oldValue === null && r.attributeName !== 'data-place') log.adds.push(r.attributeName);
    if (r.attributeName === 'data-place' && el.dataset.place === 'sheet' && log.first === null) {
      log.first = 'pending';
      requestAnimationFrame(() => { log.first = { open: el.hasAttribute('data-open'), anims: el.getAnimations().map((x) => x.transitionProperty || x.animationName || 'an animation') }; });
    } } });
  mo.observe(document.body, { subtree: true, attributes: true, attributeOldValue: true, attributeFilter: ['data-place', 'data-unfold', 'data-fold', 'data-open'] });
  window.__unwatch = () => mo.disconnect(); return 1; })()"""
NEXT_FRAME_GONE = f"new Promise((r) => requestAnimationFrame(() => r(!{SHEET['live']})))"


def motion(c, rig, rows: Rows, a: str, b: str) -> dict:
    from tests.helpers.chrome_driver import emulate_motion
    out: dict = {}
    t0 = time.time() - 40
    try:
        for m in ("reduce", "no-preference"):
            emulate_motion(c, m)
            _s3(c, rig, rows, a, b, t0, "live")
            got: dict = {"media": c.js("matchMedia('(prefers-reduced-motion: reduce)').matches")}
            c.js(WATCH)
            open_on(c, "live", f"{LW}.querySelector('[data-member=k1]')")
            wait_or(c, "window.__sheet.first && window.__sheet.first !== 'pending'", 5)
            got["first"] = c.js("window.__sheet.first")
            got["opened"] = c.js("window.__sheet.adds.slice()")
            got["anims"] = c.js(f"{SHEET['live']}?.getAnimations().length ?? null")
            c.js("document.activeElement?.blur?.(); 1")
            c.key("Escape")
            got["next_frame_gone"] = c.js(NEXT_FRAME_GONE)
            got["gone"] = bool(wait_or(c, gone("live"), 20))
            got["adds"] = c.js("window.__sheet.adds.slice()")
            c.js("window.__unwatch(); 1")
            out[m] = got
    finally:
        emulate_motion(c, "no-preference")
    return {"motion": out}


# ---- body: it alone scrolls; Last said ---------------------------------------------------------------------------------
def body(c, rig, rows: Rows, a: str, b: str) -> dict:
    out: dict = {}
    t0 = time.time() - 40
    _s3(c, rig, rows, a, b, t0, "live", extra=14)
    open_on(c, "live", f"{LW}.querySelector('[data-box=\"group:1\"] [data-testid=map-group-name]')")
    wait_or(c, f"!!{SHEET['live']}?.querySelector('[data-testid=map-step-in-said]')", 10)
    out["first"] = parts(c, "live")
    x, y, w, h = c.rect(f"{SHEET['live']}.querySelector('[data-testid=map-step-in-body]')")
    c.mouse("mouseMoved", x + w / 2, y + h / 2)
    c.call("Input.dispatchMouseEvent", type="mouseWheel", x=x + w / 2, y=y + h / 2, deltaX=0, deltaY=120)
    wait_or(c, f"({SHEET['live']}?.querySelector('[data-testid=map-step-in-body]')?.scrollTop || 0) > 0", 10)
    frames(c, 2)
    out["after"] = parts(c, "live")
    return {"body": out}


STEPS = (place, closers, motion, body)


class SheetDriver(LiveNowDriver):
    """tests/helpers/studio_live_now_steps.py's rig (its session, the clock, the motion setting), these steps."""

    @contextmanager
    def session(self, c):
        want, self.argv = self.argv, []
        with super().session(c) as theirs:
            self.argv = want
            args = theirs[0][1]
            yield tuple((fn, args) for fn in STEPS if not want or fn.__name__ in want)


if __name__ == "__main__":
    sys.exit(SheetDriver(sys.argv[1:]).main())
