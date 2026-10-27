"""tests.helpers.studio_fleet_probe -- the steps of tests/helpers/studio_fleet_layout.py
(Halo 3.1.4.0 R1): what the page shows at the default Fleet layout, measured in
headless Chrome. Each step returns a dict the checks in
tests/helpers/studio_ui_fleet_layout.py read: `layout` (which panels open,
the one click that opens each strip, Reset layout, an older saved arrangement
kept), `widths` (the log line, narrow wrapped text, the SVG scales, the glance
faces at 12 px) and `mission` (the how-it-works lines folding)."""
from __future__ import annotations

import json
import time

from tests.helpers.studio_header_menus import close_menus, more, plus_rows

WS = "document.querySelector('.workspace[data-section=\"fleet\"]')"
PANELS = f"""Object.fromEntries([...{WS}.querySelectorAll('.ws-cell')].map((c) => {{
  const p = c.querySelector('.panel'); const r = c.getBoundingClientRect();
  return [c.dataset.panel, {{collapsed: !!p.dataset.collapsed, face: p.dataset.face, body: !!p.querySelector('.panel-body:not([hidden])'),
           x: Math.round(r.x), y: Math.round(r.y), w: Math.round(r.width), h: Math.round(r.height)}}];
}}))"""
OVERLAPS = f"""(() => {{ const cells = [...{WS}.querySelectorAll('.ws-cell')].map((c) => [c.dataset.panel, c.getBoundingClientRect()]); const out = [];
  for (const [a, r] of cells) for (const [b, q] of cells) if (a < b && r.left < q.right - 1 && q.left < r.right - 1 && r.top < q.bottom - 1 && q.top < r.bottom - 1) out.push(a + '/' + b);
  return out; }})()"""

ROWS_FN = """const rowsOf = (node) => { const rg = document.createRange(); rg.selectNodeContents(node);
  return new Set([...rg.getClientRects()].filter((r) => r.width > 0).map((r) => Math.round(r.top))).size; };"""

# Every rendered HTML element in a Fleet panel body with its own text: narrower than 100 px AND wrapped onto more rows = an offender.
NARROW = f"""(() => {{ {ROWS_FN}
  const out = [];
  for (const body of {WS}.querySelectorAll('.panel-body:not([hidden])')) {{
    const panel = body.closest('.ws-cell').dataset.panel;
    for (const el of body.querySelectorAll('*')) {{
      if (el instanceof SVGElement || !el.getClientRects().length || getComputedStyle(el).visibility === 'hidden') continue;
      const texts = [...el.childNodes].filter((n) => n.nodeType === 3 && n.textContent.trim());
      if (!texts.length) continue;
      const w = el.getBoundingClientRect().width; const rows = Math.max(...texts.map(rowsOf));
      if (w < 100 && rows > 1) out.push({{panel, cls: String(el.className || el.tagName), w: Math.round(w), rows, text: el.textContent.trim().slice(0, 40)}});
    }}
  }}
  return out;
}})()"""

LOG_TEXT = f"""(() => {{ {ROWS_FN}
  const line = [...document.querySelectorAll('[data-testid="fleet-log-line"][data-kind="state"]')].find((l) => l.textContent.includes('running'));
  if (!line) return null;
  const t = line.querySelector('.fac-text'); const r = t.getBoundingClientRect();
  const head = ['.fac-ts', '.fac-kind', '.fac-who'].map((s) => line.querySelector(s).getBoundingClientRect());
  return {{w: Math.round(r.width), rows: rowsOf(t.firstChild), text: t.textContent, who: line.querySelector('.fac-who').textContent,
           log_w: Math.round(document.querySelector('[data-testid="fleet-log"]').getBoundingClientRect().width),
           head_one_row: head.every((h) => h.top < head[0].bottom && head[0].top < h.bottom), text_below: head.every((h) => r.top >= h.bottom - 1)}};
}})()"""

# The SVGs drawn at a scale: rendered px per SVG unit (the timeline's 116-unit name column, the map's cards).
SVG_SCALE = """Object.fromEntries([['timeline', '.ftl-svg'], ['map', '.fm-svg']].map(([k, s]) => { const e = document.querySelector(s);
  return [k, e ? Math.round(100 * e.getBoundingClientRect().width / e.viewBox.baseVal.width) / 100 : null]; }))"""

GLANCE_FONTS = f"""(() => {{
  const small = []; let least = 99; const faces = [];
  for (const body of {WS}.querySelectorAll('.panel-body.face-glance')) {{
    const panel = body.closest('.ws-cell').dataset.panel; faces.push(panel);
    for (const el of body.querySelectorAll('*')) {{
      if (el instanceof SVGElement || el.closest('.metric-value') || !el.getClientRects().length) continue;
      if (![...el.childNodes].some((n) => n.nodeType === 3 && n.textContent.trim())) continue;
      const px = parseFloat(getComputedStyle(el).fontSize); least = Math.min(least, px);
      if (px < 12) small.push({{panel, cls: String(el.className), px, text: el.textContent.trim().slice(0, 30)}});
    }}
  }}
  return {{least, small, faces}};
}})()"""
OVERFLOW = f"""[...{WS}.querySelectorAll('.panel-body.face-glance')].filter((b) => b.scrollHeight > b.clientHeight + 2)
  .map((b) => b.closest('.ws-cell').dataset.panel + ':' + b.scrollHeight + '>' + b.clientHeight)"""

STRIPS = ("fleet-health", "fleet-capabilities", "fleet-agent", "fleet-mission")
OPEN_BTN = "document.querySelector('.ws-cell[data-panel=\"{0}\"] .panel-bar button[aria-label=\"Open\"]')"  # the strip's chevron
NODE = "document.querySelector('[data-testid=\"fleet-node\"]')"
SAVED = "localStorage.getItem('halo.studio.layout.fleet')"

# The 3.1.3.0 default as a saved arrangement (v2): nine panels open where they were.
OLD = {"fleet-people": (0, 0, 8, 14, "glance"), "fleet-costs": (8, 0, 8, 14, "glance"), "fleet-health": (16, 0, 8, 14, "glance"),
       "fleet-attention": (0, 14, 5, 40, "detail"), "fleet-map": (5, 14, 11, 40, "detail"), "fleet-activity": (0, 54, 5, 32, "detail"),
       "fleet-mission": (5, 54, 11, 32, "detail"), "fleet-capabilities": (16, 14, 8, 18, "glance"), "fleet-agent": (16, 32, 8, 54, "detail")}


def old_saved() -> str:
    panels = {k: {"x": x, "y": y, "w": w, "h": h, "collapsed": False, "floating": False, "fx": 48, "fy": 48, "fw": 480, "fh": 320, "face": f, "z": 0}
              for k, (x, y, w, h, f) in OLD.items()}
    return json.dumps({"v": 2, "panels": panels})


def _open(c, rig, extra: str = "") -> None:
    """A fresh page load (through about:blank: the same URL again would only move to its #fragment)."""
    c.go("about:blank")
    c.wait("location.href === 'about:blank'", 10)
    c.go(rig.url(extra))
    c.wait(f"{WS} && {WS}.querySelectorAll('.ws-cell').length === 9", 40)
    c.wait(f"!!{NODE}", 30)


def _click(c, expr: str) -> None:
    """Scroll the element into view (a strip or a line below the fold), then click its middle."""
    c.js(f"{expr}.scrollIntoView({{block: 'nearest'}}); 1")
    time.sleep(0.2)
    c.click_on(expr)


def _settle(c, expr: str, timeout: float = 10):
    """`expr` once it returns the same JSON twice in a row (the grid has stopped moving)."""
    last, end = None, time.time() + timeout
    while time.time() < end:
        got = c.js(expr)
        if got == last:
            return got
        last = got
        time.sleep(0.3)
    return last


def layout(c, rig) -> dict:
    out: dict = {}
    _open(c, rig)
    out["fresh"] = _settle(c, PANELS)
    out["saved_fresh"] = c.js(SAVED)
    out["rail_strips"] = [r[3] for r in plus_rows(c) if "strip" in r[2]]  # 3.3.2.0 R2: the header's "+" menu marks them
    close_menus(c)
    out["opened"] = {}
    for pid in STRIPS:  # the one click: the chevron on the strip's title bar ("Open the panel")
        _click(c, OPEN_BTN.format(pid))
        c.wait(f"{WS}.querySelector('.ws-cell[data-panel=\"{pid}\"] .panel-body:not([hidden])') && 1", 10)
        out["opened"][pid] = {"panels": _settle(c, PANELS), "overlaps": c.js(OVERLAPS)}
    out["saved_after_open"] = bool(c.js(SAVED))
    more(c, "layout-reset")  # Reset layout (3.3.2.0 R2: the header's ... menu): the new default again
    c.wait(f"!{SAVED} && 1", 10)
    out["after_reset"] = _settle(c, PANELS)
    _click(c, NODE)  # picking an agent opens Agent's strip; the map and Activity stay where they are
    c.wait(f"{WS}.querySelector('[data-testid=\"fleet-agent-detail\"]') && 1", 30)
    out["after_pick"] = {"panels": _settle(c, PANELS), "overlaps": c.js(OVERLAPS)}
    c.js(f"localStorage.setItem('halo.studio.layout.fleet', {json.dumps(old_saved())}); 1")
    _open(c, rig)
    out["old_saved"] = _settle(c, PANELS)
    out["old_kept"] = c.js(SAVED) == old_saved()
    out["old_log"] = c.wait(LOG_TEXT, 20)  # the owner's 3.1.3.0 width (Activity 5 columns): the two-row form
    c.js("localStorage.removeItem('halo.studio.layout.fleet'); 1")
    return out


def _faces_to(c, face: str) -> None:
    """Open every strip and turn every panel to one face with its Compact / Expand toggle ("glance": compact)."""
    for pid in STRIPS:
        if c.js(f"!!{OPEN_BTN.format(pid)}"):
            _click(c, OPEN_BTN.format(pid))
            time.sleep(0.3)
    from tests.helpers.studio_full import toggle_face
    for pid in c.js(f"[...{WS}.querySelectorAll('.ws-cell')].map((c) => c.dataset.panel)"):
        cell = f'.ws-cell[data-panel="{pid}"]'  # 3.3.2.0 R3: Compact / Expand is the ... menu's face row
        if c.js(f"document.querySelector({cell!r} + ' .panel').dataset.face !== {face!r}"):
            if toggle_face(c, cell, must=False):
                time.sleep(0.3)


def widths(c, rig) -> dict:
    out: dict = {}
    _open(c, rig)
    out["log"] = c.wait(LOG_TEXT, 20)
    _settle(c, PANELS)
    out["narrow"] = c.js(NARROW)
    out["svg"] = c.js(SVG_SCALE)
    out["glance"] = c.js(GLANCE_FONTS)
    out["glance_overflow"] = c.js(OVERFLOW)
    _click(c, NODE)  # the agent picked: Agent opens in the right column
    c.wait(f"{WS}.querySelector('[data-testid=\"fleet-agent-detail\"]') && 1", 30)
    for pid in STRIPS:
        if c.js(f"!!{OPEN_BTN.format(pid)}"):
            _click(c, OPEN_BTN.format(pid))
            time.sleep(0.4)
    _settle(c, PANELS)
    out["narrow_opened"] = c.js(NARROW)
    _faces_to(c, "detail")  # People, Costs, Health and Capabilities on their full faces too
    out["expanded"] = {k: p["face"] for k, p in (_settle(c, PANELS) or {}).items()}
    out["narrow_expanded"] = c.js(NARROW)
    _faces_to(c, "glance")
    _settle(c, PANELS)
    out["all_glance"] = c.js(GLANCE_FONTS)
    out["all_glance_overflow"] = c.js(OVERFLOW)
    c.js("localStorage.removeItem('halo.studio.layout.fleet'); 1")
    return out


HOW = "document.querySelectorAll('[data-testid=\"fleet-mission-how\"] li')"
FOLD = "document.querySelector('[data-testid=\"fleet-mission-how-fold\"]')"
# The five lines: how many there are, how many show, and the fold line (its text, open or not).
HOW_NOW = f"""(() => {{ const f = {FOLD}; const li = [...{HOW}];
  return {{lines: li.length, shown: li.filter((l) => l.checkVisibility()).length, fold: !!f, open: !!(f && f.open),
           summary: f ? f.querySelector('summary').textContent : null}}; }})()"""
GOAL = "document.querySelector('[data-testid=\"fleet-mission-goal\"]')"


def mission(c, rig) -> dict:
    out: dict = {}
    _open(c, rig)
    _click(c, OPEN_BTN.format("fleet-mission"))  # Mission is a strip by default: its chevron opens it
    c.wait(f"document.querySelector('[data-testid=\"fleet-mission-start\"]') && {GOAL} && 1", 15)
    out["empty"] = c.wait(f"{HOW}.length && {HOW_NOW}", 15)  # no goal, no mission: the five lines in full
    _click(c, GOAL)
    c.type_text("scan the lab network")
    out["typed"] = c.wait(f"{FOLD} && {HOW_NOW}", 10)  # a goal typed: one "How this works" line
    _click(c, f"{FOLD}.querySelector('summary')")  # the line opens on click
    out["opened"] = c.wait(f"{FOLD}?.open && {HOW_NOW}", 10)
    rig.seed_mission()
    c.js("localStorage.removeItem('halo.studio.layout.fleet'); 1")  # the chevron saved the layout: back to the default
    _open(c, rig)  # a mission exists: the lines start folded with no goal text
    _click(c, OPEN_BTN.format("fleet-mission"))
    out["with_mission"] = c.wait(f"document.querySelector('[data-testid=\"fleet-mission-row\"]') && {HOW_NOW}", 20)
    out["goal_empty"] = c.js(f"{GOAL}?.value === ''")
    c.js("localStorage.removeItem('halo.studio.layout.fleet'); 1")
    return out
