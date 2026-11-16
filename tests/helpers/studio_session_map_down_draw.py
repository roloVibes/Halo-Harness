"""tests.helpers.studio_session_map_down_draw -- Session's Live drawer drawn top to bottom, readable, never cut, held
still (Halo 3.6.0.2 "Session map", R7 R10 R11 R12), in headless Chrome over tests/helpers/studio_session_rig.py: the
rig's session put on a seeded map per step (tests/helpers/studio_session_map_down.py `Rows`), its agents set per frame.
No model is called.

    pair    1280 x 800, `seven` (main + 7, every line main -> box): main alone, two 184 px boxes a row, nothing sideways (R7)
    long    a box whose agent has a 70-character name and a 'Bash: ' + 80-character command: whole, wrapped, measured (R10)
    cut     1280 x 800, 1440 x 900, 1920 x 1080 (and 1280 x 640), `seven` and `tiers`: no box cut at rest; the boxes below
            are counted in "↓ {n} more below" and a press scrolls one row (R11)
    hold    the pointer on main: a new box and new words move nothing; it leaves: the box is drawn; after a hand scroll
            the first box seen keeps its place when a box arrives above it (R12)
    still   the head's buttons and the slot keep their rects across 20 frames of new words and zoom percents (R12)
    gone    a hand scroll, then the drawer closed at once: no timer of the drawing fires once it is gone (batch 7)

    python -m tests.helpers.studio_session_map_down_draw
The last stdout line is a JSON object of what it saw.
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

from tests.helpers.studio_session_map_down import MapDownDriver, Rows, _reload  # noqa: E402

SEVEN_BOXES = ("planner", "researcher", "coder", "reviewer", "writer", "media-reader", "ops")
SEVEN = {"format": "map/1", "name": "seven", "main": {"agent": "main"}, "boxes": [{"id": n, "agent": n} for n in SEVEN_BOXES],
         "lines": [{"from": "main", "to": n, "when": "main-decides"} for n in SEVEN_BOXES]}
TIERS = {"format": "map/1", "name": "tiers", "main": {"agent": "main"},
         "boxes": [{"id": "plan", "agent": "planner"}, {"id": "research", "agent": "researcher"}, {"id": "code", "agent": "coder"},
                   {"id": "docs", "agent": "writer"}, {"id": "review", "agent": "reviewer"}, {"id": "check", "workflow": "review"}],
         "lines": [{"from": "main", "to": "plan", "when": "always"}, {"from": "main", "to": "research", "when": "main-decides"},
                   {"from": "plan", "to": "code", "when": "always"}, {"from": "plan", "to": "docs", "when": {"says": ["docs"]}},
                   {"from": "research", "to": "code", "when": "ask"}, {"from": "code", "to": "review", "when": "always"},
                   {"from": "code", "to": "check", "when": "main-decides"}]}
LONG = ("reviewer_" * 8)[:70]
CMD = "x" * 80
LONGMAP = {"format": "map/1", "name": "longname", "main": {"agent": "main"}, "boxes": [{"id": "long", "agent": LONG}],
           "lines": [{"from": "main", "to": "long", "when": "always"}]}
SCOUT = "made-up:scout01"
MORE = "↓ %d more below"  # R11, section 4 (truthWords.ts moreBelow)

M = "document.querySelector('[data-testid=\"session-lit-map\"]')"
READ = f"""(() => {{ const m = {M}; if (!m) return null;
  const sc = m.querySelector('.mp-mini-scroll'), w = m.querySelector('.mp-mini-world');
  const R = (e) => {{ if (!e) return null; const r = e.getBoundingClientRect(); return [r.left, r.top, r.width, r.height]; }};
  return {{map: m.dataset.map, dir: m.dataset.dir || '', zoom: +((w && w.dataset.zoom) || 0), sc: R(sc), cw: sc.clientWidth, sw: sc.scrollWidth,
          st: sc.scrollTop, gutter: getComputedStyle(sc).scrollbarGutter, held: !!m.dataset.held,
          boxes: [...m.querySelectorAll('[data-testid=session-lit-box]')].map((b) => [b.dataset.box, ...R(b)]),
          below: (m.querySelector('[data-testid=map-more-below]') || {{}}).textContent || '', slot: R(m.querySelector('[data-testid=session-map-below]')),
          head: ['session-lit-open', 'canvas-zoom-out', 'canvas-zoom-level', 'canvas-zoom-in', 'canvas-fit'].map((t) => R(m.querySelector(`[data-testid=${{t}}]`))),
          fit: (f => f ? getComputedStyle(f).visibility : '')(m.querySelector('[data-testid=canvas-fit]'))}}; }})()"""
LONG_READ = f"""(() => {{ const b = {M}?.querySelector('[data-testid=session-lit-box][data-box=long]'); if (!b) return null;
  const n = b.querySelector('.mp-name'), rows = [...b.querySelectorAll('.mp-lit-row')];
  const cs = (e) => {{ const s = getComputedStyle(e); return [s.overflowWrap, s.textOverflow, s.webkitLineClamp || s.getPropertyValue('-webkit-line-clamp') || 'none']; }};
  return {{name: n.textContent, css: [n, ...rows].map(cs), name_sw: n.scrollWidth, name_cw: n.clientWidth, h: b.getBoundingClientRect().height,
          sh: b.scrollHeight, zoom: +{M}.querySelector('.mp-mini-world').dataset.zoom, rows: rows.map((r) => r.textContent)}}; }})()"""


def _seed(rig) -> None:
    from halo_harness.crew import store
    for m in (SEVEN, TIERS, LONGMAP):
        store.write_text(store.path_for("map", m["name"], state_dir=rig.state), json.dumps(m))


def _agents(rows: Rows, sid: str, main: str = "done", current: str = "", extra=()) -> list:
    """The session's agent rows: its main (state `main`, doing `current`) and `extra` (name, state, current) under main."""
    base = next((r for r in rows.orig() if r.get("session_id") == sid), {})
    have = base.get("agents") or []
    head = next((a for a in have if a.get("agent_id") == "main"), {"agent_id": "main", "name": "main", "kind": "main"})
    tmpl = next((a for a in have if a.get("agent_id") != "main"), {})
    out = [{**head, "state": main, "current": current}]
    for aid, name, state, cur in extra:
        out.append({**tmpl, "agent_id": aid, "name": name, "role": name, "parent": "main", "kind": "member", "state": state,
                    "current": cur, "crew": None, "square": None, "task": f"{name}'s task"})
    return out


def _size(c, w: int, h: int) -> None:
    c.call("Emulation.setDeviceMetricsOverride", width=w, height=h, deviceScaleFactor=1, mobile=False)


def _open(c, rig, rows: Rows, a: str, mp: str, w: int, h: int, n: int, **agents) -> dict:
    from tests.helpers.studio_session import boot_go, url
    rows.reset()
    rows.set(a, map=mp, busy=False, status="idle", agents=_agents(rows, a, **agents))
    _size(c, w, h)
    boot_go(c, url(rig, f"mode=session&session={a}&open=session-map"))  # the Live drawer alone open, as at a start
    c.wait(f"!!{M} && {M}.dataset.map === '{mp}' && {M}.querySelectorAll('[data-testid=session-lit-box]').length >= {n}", 40)
    c.js("performance.setResourceTimingBufferSize(100000); 1")
    c.mouse("mouseMoved", w - 1, h - 1)  # the pointer out of the drawer (it is on the left)
    return _settled(c)


def _settled(c, tries: int = 12) -> dict:
    """The drawing once two reads 500 ms apart give the same boxes."""
    last = c.js(READ) or {}
    for _ in range(tries):
        time.sleep(0.5)
        now = c.js(READ) or {}
        if now.get("boxes") == last.get("boxes") and now.get("sc") == last.get("sc"):
            return now
        last = now
    return last


def pair(c, rig, rows, a) -> dict:
    return {"pair": _open(c, rig, rows, a, "seven", 1280, 800, 8)}


def long(c, rig, rows, a) -> dict:
    _open(c, rig, rows, a, "longname", 1440, 900, 2, extra=(("lng00001", LONG, "running", "Bash: " + CMD),))
    c.wait(f"{M}.querySelector('[data-box=long]')?.dataset.state === 'working'", 15)
    d = _settled(c)
    return {"long": {**(c.js(LONG_READ) or {}), "boxes": d.get("boxes")}}


def cut(c, rig, rows, a) -> dict:
    out = []
    for (w, h), mp, n in (((1280, 800), "seven", 8), ((1440, 900), "seven", 8), ((1920, 1080), "seven", 8),
                          ((1280, 800), "tiers", 7), ((1440, 900), "tiers", 7), ((1920, 1080), "tiers", 7), ((1280, 640), "seven", 8)):
        before = _open(c, rig, rows, a, mp, w, h, n)
        one = {"size": [w, h], "map": mp, "before": before, "after": None}
        if before.get("below"):
            c.click_on(f"{M}.querySelector('[data-testid=map-more-below]')")
            c.mouse("mouseMoved", w - 1, h - 1)
            one["after"] = _settled(c)
        out.append(one)
    return {"cut": out}


def _rects(d: dict) -> dict:
    return {b[0]: b[1:] for b in d.get("boxes") or []}


def hold(c, rig, rows, a) -> dict:
    out: dict = {}
    w, h = 1440, 600
    first = _open(c, rig, rows, a, "tiers", w, h, 7)
    out["rest"] = first
    x, y, bw, bh = _rects(first).get("main") or [0, 0, 0, 0]
    c.mouse("mouseMoved", x + bw / 2, y + bh / 2)
    rows.set(a, agents=_agents(rows, a, main="running", current="Bash: ls -la", extra=(("scout01", "scout", "running", "Read: notes"),)))
    _reload(c, rows, 2)
    c.wait(f"{M}.querySelector('[data-box=main]')?.dataset.state === 'working'", 15)
    samples = []
    for _ in range(12):
        samples.append(_rects(c.js(READ) or {}))
        time.sleep(0.25)
    out["under"] = samples
    out["held"] = (c.js(READ) or {}).get("held")
    c.mouse("mouseMoved", w - 1, h - 1)
    t0 = time.time()
    try:
        c.wait(f"!!{M}.querySelector('[data-box=\"{SCOUT}\"]')", 2)
        out["arrived_s"] = round(time.time() - t0, 2)
    except TimeoutError:
        out["arrived_s"] = None
    # after a hand scroll the first box he sees keeps its place when a box arrives above it
    rows.set(a, agents=_agents(rows, a))
    _reload(c, rows)
    c.wait(f"!{M}.querySelector('[data-box=\"{SCOUT}\"]')", 15)
    for _ in range(2):
        c.js(f"{M}.querySelector('[data-testid=canvas-zoom-in]').click(); 1")
        time.sleep(0.3)
    d = _settled(c)
    code = _rects(d).get("code")
    c.js(f"(() => {{ const s = {M}.querySelector('.mp-mini-scroll'); s.scrollTop += {code[1] - d['sc'][1] - 4 if code else 0}; return 1; }})()")
    time.sleep(0.6)
    before = c.js(READ) or {}
    top = before["sc"][1] if before.get("sc") else 0
    seen = sorted((r[1], k) for k, r in _rects(before).items() if r[1] + r[3] > top + 0.5)
    out["scrolled"] = {"st": before.get("st"), "zoom": before.get("zoom"), "first": seen[0][1] if seen else None,
                       "top": seen[0][0] if seen else None}
    rows.set(a, agents=_agents(rows, a, extra=(("scout01", "scout", "running", "Read: notes"),)))
    _reload(c, rows)
    c.wait(f"!!{M}.querySelector('[data-box=\"{SCOUT}\"]')", 15)
    time.sleep(0.6)
    after = c.js(READ) or {}
    f = out["scrolled"]["first"]
    out["kept"] = {"first": f, "top": (_rects(after).get(f) or [None, None])[1], "st": after.get("st"),
                   "moved": f and (_rects(after).get(f) or [0, 0])[1] is not None}
    return {"hold": out}


def still(c, rig, rows, a) -> dict:
    w, h = 1440, 900
    first = _open(c, rig, rows, a, "seven", w, h, 8)
    frames = []
    for i in range(20):
        if i % 2 == 0:
            rows.set(a, agents=_agents(rows, a, main="running", current="Bash: " + "word " * (1 + i)))
            _reload(c, rows)
        else:
            c.js(f"{M}.querySelector('[data-testid={'canvas-zoom-in' if i % 4 == 1 else 'canvas-zoom-out'}]').click(); 1")
            time.sleep(0.15)
        d = c.js(READ) or {}
        frames.append({"head": d.get("head"), "slot": d.get("slot"), "zoom": d.get("zoom"), "fit": d.get("fit")})
    return {"still": {"first": {"head": first.get("head"), "slot": first.get("slot"), "fit": first.get("fit")}, "frames": frames}}


# batch 7: every timeout the drawing sets from its own scroll handler is tagged; once the drawing is gone none may fire
GONE = f"""(() => {{ const m = {M}, sc = m && m.querySelector('.mp-mini-scroll'); if (!sc) return null;
  const T = window.__gone = {{made: 0, fired: 0, firedGone: 0}}, set = window.setTimeout;
  window.setTimeout = function (fn, ms, ...rest) {{
    const e = window.event, mine = e && e.type === 'scroll' && e.target && e.target.closest && e.target.closest('[data-testid=session-lit-map]');
    if (!mine) return set.call(window, fn, ms, ...rest);
    T.made++;
    return set.call(window, function () {{ T.fired++; if (!document.querySelector('[data-testid=session-lit-map]')) T.firedGone++;
      return typeof fn === 'function' ? fn.apply(this, arguments) : undefined; }}, ms, ...rest);
  }};
  sc.dispatchEvent(new Event('scroll'));
  const x = document.querySelector('.ws-cell[data-panel="session-map"] [data-testid=panel-collapse]')
         || document.querySelector('.section-view:not([hidden]) [data-testid="viewbar-btn"][data-panel="session-map"]');
  if (x) x.click();
  return {{made: T.made, closer: !!x}}; }})()"""


def gone(c, rig, rows, a) -> dict:
    """A hand scroll starts the drawing's settle timer; the drawer closes at once: nothing of the drawing fires after."""
    _open(c, rig, rows, a, "seven", 1280, 640, 8)
    start = c.js(GONE) or {}
    c.wait(f"!{M}", 10)
    time.sleep(0.8)  # the settle timer is 200 ms: well past it
    return {"gone": {**start, **(c.js("window.__gone || {}") or {}), "drawn": c.js(f"!!{M}")}}


class DrawDriver(MapDownDriver):
    width, height = 1280, 800

    @contextmanager
    def session(self, c):
        from tests.helpers.studio_session import ERRS_JS
        from tests.helpers.studio_session_rig import StudioSessionRig
        with StudioSessionRig() as rig:
            _seed(rig)
            rows = Rows(rig)
            c.call("Page.addScriptToEvaluateOnNewDocument", source=ERRS_JS)
            args = (c, rig, rows, rig.act.session_id)
            steps = [s for s in (pair, long, cut, hold, still, gone) if not self.argv or s.__name__ in self.argv]
            yield tuple((fn, args) for fn in steps)


if __name__ == "__main__":
    sys.exit(DrawDriver(sys.argv[1:]).main())
