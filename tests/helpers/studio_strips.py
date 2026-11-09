"""tests.helpers.studio_strips -- Halo 3.3.15.0 R3, owner feedback 2026-11-09 "panels breathe": the collapsed strips of
a section and an open panel's frame, measured in headless Chrome. Used by tests/helpers/studio_textboxes.py (the steps
`fleet_strips` and `session_strips`, on the Prompt rig's Studio): every panel collapsed, each strip's height, its title
bar centred in it, its side padding, the gaps between strips and to the workspace's edges; then one panel opened: its
title bar's height and its body's padding."""
from __future__ import annotations

COLLAPSE_ALL = """(() => { const ws = [...document.querySelectorAll('.workspace')].find((w) => w.offsetParent);
  const open = [...ws.querySelectorAll('.ws-cell:not([data-floating]) [data-testid="panel-strip"][aria-expanded="true"]')];
  open.forEach((b) => b.click()); return open.length; })()"""

STILL_OPEN = """(() => { const ws = [...document.querySelectorAll('.workspace')].find((w) => w.offsetParent);
  return ws.querySelectorAll('.ws-cell:not([data-floating]) [data-testid="panel-strip"][aria-expanded="true"]').length; })()"""

MEASURE = """(() => { const ws = [...document.querySelectorAll('.workspace')].find((w) => w.offsetParent), W = ws.getBoundingClientRect();
  const strips = [...ws.querySelectorAll('.ws-cell:not([data-floating]) > .panel[data-collapsed]')].map((p) => {
    const r = p.getBoundingClientRect(), bar = p.querySelector('.panel-bar'), cs = getComputedStyle(bar);
    const mid = (el) => { const b = el.getBoundingClientRect(); return b.top + b.height / 2; };
    const off = [bar.querySelector('.panel-title'), bar.querySelector('[data-testid="panel-strip"]')].filter(Boolean)
      .map((el) => Math.abs(mid(el) - (r.top + r.height / 2)));
    return {id: p.closest('.ws-cell').dataset.panel, h: r.height, top: r.top, bottom: r.bottom, left: r.left, right: r.right,
            pad: [parseFloat(cs.paddingLeft), parseFloat(cs.paddingRight)], off: Math.max(0, ...off)}; });
  let hgap = 999, vgap = 999;
  for (const a of strips) for (const b of strips) {
    if (a === b) continue;
    const sameRow = a.top < b.bottom && b.top < a.bottom, sameCol = a.left < b.right && b.left < a.right;
    if (sameRow && b.left >= a.right - 1) hgap = Math.min(hgap, b.left - a.right);
    if (sameCol && b.top >= a.bottom - 1) vgap = Math.min(vgap, b.top - a.bottom);
  }
  const edge = strips.length ? Math.min(...strips.map((s) => Math.min(s.left - W.left, W.right - s.right, s.top - W.top, W.bottom - s.bottom))) : 0;
  return {n: strips.length, heights: strips.map((s) => Math.round(s.h * 10) / 10), hgap, vgap, edge,
          pad: Math.min(...strips.map((s) => Math.min(...s.pad))), off: Math.max(0, ...strips.map((s) => s.off))}; })()"""

OPEN_ONE = """(() => { const ws = [...document.querySelectorAll('.workspace')].find((w) => w.offsetParent);
  const cell = ws.querySelector('.ws-cell[data-panel="{pid}"]'); cell.querySelector('[data-testid="panel-strip"]').click(); return 1; })()"""

FRAME = """(() => { const cell = document.querySelector('.ws-cell[data-panel="{pid}"]'), body = cell.querySelector('.panel-body:not([hidden])');
  const cs = getComputedStyle(body), bar = cell.querySelector('.panel-bar');
  return {pid: '{pid}', bar: bar.getBoundingClientRect().height,
          body_pad: Math.min(...['Top', 'Right', 'Bottom', 'Left'].map((k) => parseFloat(cs['padding' + k])))}; })()"""


def strips(c, url: str, ready: str, open_pid: str, shot=None, name: str = "") -> dict:
    """Load `url`, collapse every grid panel, measure the strips; then open `open_pid` and measure its frame."""
    c.go("about:blank")
    c.go(url)
    c.wait(ready, 40)
    for _ in range(3):  # a panel that opens on its own as the page settles is collapsed on the next pass
        c.js(COLLAPSE_ALL)
        c.wait(f"{STILL_OPEN} === 0", 10)
    got = c.wait(f"(() => {{ const m = {MEASURE}; return m.n > 0 && m; }})()", 10)
    if shot:
        shot(c, f"{name}-strips")
    c.js(OPEN_ONE.replace("{pid}", open_pid))
    c.wait(f"!!document.querySelector('.ws-cell[data-panel=\"{open_pid}\"] [data-testid=\"panel-strip\"][aria-expanded=\"true\"]')", 10)
    got["frame"] = c.js(FRAME.replace("{pid}", open_pid))
    return got
