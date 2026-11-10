"""tests.helpers.studio_fleet_probe -- the steps of tests/helpers/studio_fleet_layout.py (Halo 3.1.4.0 R1; 3.3.16.0 R2 "the
Fleet fold": the Fleet section's nine-panel workspace went, so these measure where its pieces went -- Agents -> Live's
workspace (`roles`): the tree on the canvas, the inspector strip, Activity as an optional floating panel, the Attention
queue over the view; Runs' Mission panel). Each step returns a dict the checks in tests/helpers/studio_ui_fleet_layout.py
read: `layout` (what opens on load, the "+" row that adds Activity, Reset layout, an agent picked), `widths` (the log
line, narrow wrapped text, the timeline's scale, the glance's captions at 12 px) and `mission` (the how-it-works lines
folding)."""
from __future__ import annotations

import time

from tests.helpers.studio_header_menus import close_menus, more, plus, plus_rows

WS = "document.querySelector('.workspace[data-section=\"roles\"]')"
PANELS = f"""Object.fromEntries([...{WS}.querySelectorAll('.ws-cell')].map((c) => {{
  const p = c.querySelector('.panel'); const r = c.getBoundingClientRect();
  return [c.dataset.panel, {{collapsed: !!p.dataset.collapsed, face: p.dataset.face, body: !!p.querySelector('.panel-body:not([hidden])'),
           floating: c.dataset.floating === 'true',
           x: Math.round(r.x), y: Math.round(r.y), w: Math.round(r.width), h: Math.round(r.height)}}];
}}))"""
ROWS_FN = """const rowsOf = (node) => { const rg = document.createRange(); rg.selectNodeContents(node);
  return new Set([...rg.getClientRects()].filter((r) => r.width > 0).map((r) => Math.round(r.top))).size; };"""
BODIES = "[...document.querySelectorAll('.workspace[data-section=\"roles\"] .panel-body:not([hidden]), [data-panel=\"fleet-attention\"] .panel-body')]"

# Every rendered HTML element in a Live panel body (and the Attention queue) with its own text: narrower than 100 px AND
# wrapped onto more rows = an offender.
NARROW = f"""(() => {{ {ROWS_FN}
  const out = [];
  for (const body of {BODIES}) {{
    const panel = body.closest('[data-panel]')?.dataset.panel;
    if (panel === 'roles-graph') continue;  // the tree's nodes are fixed-size cards, measured by the Live tests
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

# The timeline is drawn at a scale: rendered px per SVG unit (its 116-unit name column).
SVG_SCALE = """(() => { const e = document.querySelector('.ftl-svg'); return {timeline: e ? Math.round(100 * e.getBoundingClientRect().width / e.viewBox.baseVal.width) / 100 : null}; })()"""

# The fleet at a glance (Live's inspector with nothing picked): every caption at least 12 px.
GLANCE_FONTS = """(() => {
  const small = []; let least = 99; const g = document.querySelector('[data-testid="live-glance"]');
  for (const el of g ? g.querySelectorAll('*') : []) {
    if (el instanceof SVGElement || !el.getClientRects().length) continue;
    if (![...el.childNodes].some((n) => n.nodeType === 3 && n.textContent.trim())) continue;
    const px = parseFloat(getComputedStyle(el).fontSize); least = Math.min(least, px);
    if (px < 12) small.push({cls: String(el.className), px, text: el.textContent.trim().slice(0, 30)});
  }
  return {least, small, glance: !!g};
})()"""
OVERFLOW = """[...document.querySelectorAll('[data-testid="live-glance"] .ri-summary dd')].filter((d) => d.scrollWidth > d.clientWidth + 2).map((d) => d.textContent.slice(0, 30))"""

NODE = "document.querySelector('[data-testid=\"roles-live-node\"]')"
SAVED = "localStorage.getItem('halo.studio.layout.roles')"
INSPECTOR_OPEN = "document.querySelector('.ws-cell[data-panel=\"roles-inspector\"] .panel-body:not([hidden])')"


def _open(c, rig, extra: str = "") -> None:
    """A fresh page load (through about:blank: the same URL again would only move to its #fragment)."""
    c.go("about:blank")
    c.wait("location.href === 'about:blank'", 10)
    c.go(rig.url(extra))
    c.wait(f"{WS} && {WS}.querySelectorAll('.ws-cell').length >= 6", 40)
    c.wait(f"!!{NODE}", 30)


def _click(c, expr: str) -> None:
    """Scroll the element into view, then click its middle."""
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
    out["closed_on_load"] = c.js("[!document.querySelector('[data-panel=\"fleet-activity\"]'), !document.querySelector('[data-panel=\"fleet-attention\"]')]")
    out["saved_fresh"] = c.js(SAVED)
    out["plus_activity"] = next((r[1] for r in plus_rows(c) if r[0] == "fleet-activity"), None)
    close_menus(c)
    plus(c, "fleet-activity")  # one row adds it, beside the tree
    c.wait("!!document.querySelector('[data-panel=\"fleet-activity\"] .panel-body:not([hidden])')", 15)
    out["added"] = (_settle(c, PANELS) or {}).get("fleet-activity")
    out["saved_after_add"] = bool(c.js(SAVED))
    more(c, "layout-reset")  # Reset layout: the default again, Activity gone, nothing saved
    c.wait(f"!{SAVED} && !document.querySelector('[data-panel=\"fleet-activity\"]') && 1", 10)
    out["after_reset"] = _settle(c, PANELS)
    _click(c, NODE)  # picking an agent opens the inspector; the tree stays where it is
    c.wait(f"{INSPECTOR_OPEN} && document.querySelector('[data-testid=\"fleet-agent-detail\"]') && 1", 30)
    pick = _settle(c, PANELS) or {}
    out["after_pick"] = {"inspector": pick.get("roles-inspector"), "graph_open": (pick.get("roles-graph") or {}).get("body") is True}
    c.js("localStorage.removeItem('halo.studio.layout.roles'); 1")
    return out


def widths(c, rig) -> dict:
    out: dict = {}
    _open(c, rig)
    plus(c, "fleet-activity")
    out["log"] = c.wait(LOG_TEXT, 20)
    from tests.helpers.studio_fleet_panels import open_strip
    open_strip(c, "roles-inspector")  # the fleet at a glance (nothing picked)
    c.wait("!!document.querySelector('[data-testid=\"live-glance\"]')", 15)
    _settle(c, PANELS)
    out["narrow"] = c.js(NARROW)
    out["svg"] = c.js(SVG_SCALE)
    out["glance"] = c.js(GLANCE_FONTS)
    out["glance_overflow"] = c.js(OVERFLOW)
    c.click_on("document.querySelector('[data-testid=\"agents-attention\"]')")  # the queue over the view
    c.wait("!!document.querySelector('[data-panel=\"fleet-attention\"] .panel-body')", 10)
    _click(c, NODE)  # the agent picked: the agent inspector
    c.wait("!!document.querySelector('[data-testid=\"fleet-agent-detail\"]')", 30)
    _settle(c, PANELS)
    out["narrow_opened"] = c.js(NARROW)
    c.js("localStorage.removeItem('halo.studio.layout.roles'); 1")
    return out


HOW = "document.querySelectorAll('[data-testid=\"fleet-mission-how\"] li')"
FOLD = "document.querySelector('[data-testid=\"fleet-mission-how-fold\"]')"
# The five lines: how many there are, how many show, and the fold line (its text, open or not).
HOW_NOW = f"""(() => {{ const f = {FOLD}; const li = [...{HOW}];
  return {{lines: li.length, shown: li.filter((l) => l.checkVisibility()).length, fold: !!f, open: !!(f && f.open),
           summary: f ? f.querySelector('summary').textContent : null}}; }})()"""
GOAL = "document.querySelector('[data-testid=\"fleet-mission-goal\"]')"


def _mission_panel(c) -> None:
    """M on Agents: Runs' Mission panel."""
    from tests.helpers.studio_agents import key
    c.js("document.activeElement?.blur(); 1")
    key(c, "m")
    c.wait(f"document.querySelector('[data-testid=\"fleet-mission-start\"]') && {GOAL} && 1", 20)


def mission(c, rig) -> dict:
    out: dict = {}
    _open(c, rig)
    _mission_panel(c)
    out["empty"] = c.wait(f"{HOW}.length && {HOW_NOW}", 15)  # no goal, no mission: the five lines in full
    _click(c, GOAL)
    c.type_text("scan the lab network")
    out["typed"] = c.wait(f"{FOLD} && {HOW_NOW}", 10)  # a goal typed: one "How this works" line
    _click(c, f"{FOLD}.querySelector('summary')")  # the line opens on click
    out["opened"] = c.wait(f"{FOLD}?.open && {HOW_NOW}", 10)
    rig.seed_mission()
    _open(c, rig)  # a mission exists: the lines start folded with no goal text
    _mission_panel(c)
    out["with_mission"] = c.wait(f"document.querySelector('[data-testid=\"fleet-mission-row\"]') && {HOW_NOW}", 20)
    out["goal_empty"] = c.js(f"{GOAL}?.value === ''")
    c.js("localStorage.removeItem('halo.studio.layout.orchestra'); 1")
    return out
