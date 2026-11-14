"""tests.helpers.studio_strips -- Halo 3.3.15.0 R3, owner feedback 2026-11-09 "panels breathe"; 3.6.0.0 R0a: the strips
became the view bar's buttons (one 44 px row over the stage, lib/workspace/ViewBar.tsx), so this measures those: every
drawer closed, each button's height, its name centred in it, its side padding, the gaps between buttons and to the
bar's ends; then one drawer opened: its title bar's height and its body's padding. Used by
tests/helpers/studio_textboxes.py (the steps `fleet_strips` and `session_strips`, on the Prompt rig's Studio)."""
from __future__ import annotations

BAR = "[...document.querySelectorAll('.section-view:not([hidden]) .viewbar')].find((b) => b.offsetParent)"

CLOSE_ALL = f"""(() => {{ const bar = {BAR}; if (!bar) return -1;
  const open = [...bar.querySelectorAll('[data-testid="viewbar-btn"][data-role="drawer"][aria-pressed="true"]')];
  open.forEach((b) => b.click()); return open.length; }})()"""

STILL_OPEN = f"""(() => {{ const bar = {BAR}; return bar ? bar.querySelectorAll('[data-testid="viewbar-btn"][data-role="drawer"][aria-pressed="true"]').length : -1; }})()"""

MEASURE = f"""(() => {{ const bar = {BAR}; if (!bar) return {{n: 0}}; const W = bar.getBoundingClientRect();
  const btns = [...bar.querySelectorAll('[data-testid="viewbar-btn"]')].filter((b) => b.getBoundingClientRect().width > 0).map((b) => {{
    const r = b.getBoundingClientRect(), cs = getComputedStyle(b), name = b.querySelector('.viewbar-name').getBoundingClientRect();
    return {{id: b.dataset.panel, h: r.height, left: r.left, right: r.right, top: r.top, bottom: r.bottom,
            pad: [parseFloat(cs.paddingLeft), parseFloat(cs.paddingRight)], off: Math.abs((name.top + name.height / 2) - (r.top + r.height / 2))}}; }});
  btns.sort((a, b) => a.left - b.left);
  let hgap = 999;
  for (let i = 1; i < btns.length; i++) hgap = Math.min(hgap, btns[i].left - btns[i - 1].right);
  const edge = btns.length ? Math.min(btns[0].left - W.left, W.right - btns[btns.length - 1].right) : 0;
  return {{n: btns.length, bar: Math.round(W.height), heights: btns.map((s) => Math.round(s.h * 10) / 10), hgap, edge,
          pad: Math.min(...btns.map((s) => Math.min(...s.pad))), off: Math.max(0, ...btns.map((s) => s.off))}}; }})()"""

OPEN_ONE = """(() => { const b = document.querySelector('.section-view:not([hidden]) [data-testid="viewbar-btn"][data-panel="{pid}"]'); b.click(); return 1; })()"""

FRAME = """(() => { const cell = document.querySelector('.stage-drawer .ws-cell[data-panel="{pid}"]'), body = cell.querySelector('.panel-body:not([hidden])');
  const cs = getComputedStyle(body), bar = cell.querySelector('.panel-bar');
  return {pid: '{pid}', bar: bar.getBoundingClientRect().height,
          body_pad: Math.min(...['Top', 'Right', 'Bottom', 'Left'].map((k) => parseFloat(cs['padding' + k])))}; })()"""


def strips(c, url: str, ready: str, open_pid: str, shot=None, name: str = "") -> dict:
    """Load `url`, close every drawer, measure the view bar's buttons; then open `open_pid` and measure its frame."""
    c.go("about:blank")
    c.go(url)
    c.wait(ready, 40)
    c.wait(f"{STILL_OPEN} >= 0", 20)
    c.js(CLOSE_ALL)
    c.wait(f"{STILL_OPEN} === 0", 10)
    got = c.wait(f"(() => {{ const m = {MEASURE}; return m.n > 0 && m; }})()", 10)
    if shot:
        shot(c, f"{name}-bar")
    c.js(OPEN_ONE.replace("{pid}", open_pid))
    c.wait(f"!!document.querySelector('.stage-drawer .ws-cell[data-panel=\"{open_pid}\"] .panel-body')", 10)
    got["frame"] = c.js(FRAME.replace("{pid}", open_pid))
    return got
