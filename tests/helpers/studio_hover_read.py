"""tests.helpers.studio_hover_read -- what tests/helpers/studio_hover.py reads off the page and how it moves the pointer
(Halo 3.3.16.1, the hover cards): the card as JSON (its kind and box, its rows, its NOW line, where it sits against its
box and the window, what overflows, its paddings, row heights and caps), the real pointer resting on a box and leaving
it (CDP Input.dispatchMouseEvent through cdp.Chrome.mouse), a Tab key. Nothing here calls a React handler."""
from __future__ import annotations

import time

CARD = "document.querySelector('[data-testid=\"hover-card\"]')"

READ = r"""(() => {
  const c = document.querySelector('[data-testid="hover-card"]');
  if (!c || c.style.visibility === 'hidden') return null;
  const b = document.querySelector('[aria-describedby="halo-hover-card"]');
  const r = (e) => { const x = e.getBoundingClientRect(); return [Math.round(x.left), Math.round(x.top), Math.round(x.right), Math.round(x.bottom)]; };
  const cs = getComputedStyle(c), dt = c.querySelector('dt'), dcs = dt ? getComputedStyle(dt) : null;
  const text = (sel) => c.querySelector(sel)?.textContent || '';
  const clamped = new Set([...c.querySelectorAll('.hc-is')]);
  return {kind: c.dataset.kind, for: c.dataset.for, by: c.dataset.by, side: c.dataset.side, role: c.getAttribute('role'),
    title: text('[data-testid="hover-card-title"]'), is: text('[data-testid="hover-card-is"]'), now: text('[data-testid="hover-card-now"]'),
    foot: text('[data-testid="hover-card-foot"]'),
    rows: [...c.querySelectorAll('[data-testid="hover-card-row"]')].map((d) => [d.dataset.row, d.querySelector('dt').textContent, d.querySelector('dd').textContent]),
    card: r(c), box: b ? r(b) : null, box_testid: b ? (b.dataset.testid || '') : '', vw: innerWidth, vh: innerHeight,
    pad: ['Top', 'Right', 'Bottom', 'Left'].map((k) => parseFloat(cs['padding' + k])),
    row_h: [...c.querySelectorAll('.hc-row')].map((e) => Math.round(e.getBoundingClientRect().height * 10) / 10),
    caps: dcs ? [dcs.textTransform, dcs.fontFamily] : null,
    over: [...c.querySelectorAll('dt, dd, .hc-title, .hc-now-v, .hc-foot')].filter((e) => !clamped.has(e) && e.scrollWidth > e.clientWidth + 1)
      .map((e) => (e.className || e.tagName) + ':' + e.textContent.slice(0, 40)),
    buttons: c.querySelectorAll('button, a, input').length, count: document.querySelectorAll('[data-testid="hover-card"]').length};
})()"""


def card_of(kind: str, key: str = "") -> str:
    """An expression: the card as READ reads it once it shows for `kind` (and box `key`), else null."""
    want = f"c.dataset.kind === '{kind}'" + (f" && c.dataset.for === {key!r}" if key else "")
    return f"(() => {{ const c = {CARD}; return c && c.style.visibility !== 'hidden' && {want} ? {READ} : null; }})()"


def rest(c, expr: str, fx: float = 0.5, fy: float = 0.5) -> None:
    """The real pointer onto `expr` (from just outside it, so the box sees it enter), then it rests there."""
    x, y, w, h = c.rect(expr)
    c.mouse("mouseMoved", max(1, x - 6), max(1, y - 6))
    c.mouse("mouseMoved", x + w * fx, y + h * fy)


def away(c, x: float = 300, y: float = 12) -> None:
    """The pointer off every box (onto the header)."""
    c.mouse("mouseMoved", x, y)


def hover_card(c, expr: str, kind: str, key: str = "", fx: float = 0.5, fy: float = 0.5, timeout: float = 10):
    """Rest on `expr` and wait for its card; a box still laying out (a re-render moved it) gets a second rest."""
    for attempt in range(2):
        c.wait(f"!!({expr})", timeout)
        rest(c, expr, fx, fy)
        try:
            return c.wait(card_of(kind, key), timeout if attempt else 4)
        except TimeoutError:
            if attempt:
                raise
            away(c)
            time.sleep(0.3)
    return None


def gone(c, timeout: float = 5):
    return c.wait(f"!{CARD} && 'gone'", timeout)


def tab(c, shift: bool = False) -> None:
    for kind in ("rawKeyDown", "keyUp"):
        c.call("Input.dispatchKeyEvent", type=kind, key="Tab", code="Tab", windowsVirtualKeyCode=9, modifiers=8 if shift else 0)


def seen_for(c, secs: float = 1.2):
    """The first card that showed at any moment over `secs` (polled): its kind, box and where the pointer rests
    (`pointer`, the box under it), or None when none did."""
    end = time.time() + secs
    while time.time() < end:
        if c.js(f"!!{CARD}"):
            got = c.js(f"(() => {{ const c = {CARD}; return {{kind: c.dataset.kind || '', for: c.dataset.for || '', by: c.dataset.by || '',"
                       " box: document.querySelector('[aria-describedby=\"halo-hover-card\"]')?.dataset.testid || ''}; })()") or {}
            at = getattr(c, "pointer", None)
            got["pointer"] = at
            if at:
                got["under_pointer"] = c.js(f"document.elementFromPoint({at[0]}, {at[1]})?.closest('[data-testid]')?.dataset.testid || ''")
            return got
        time.sleep(0.1)
    return None


def none_for(c, secs: float = 1.2) -> bool:
    """No card at any moment over `secs` (polled)."""
    return seen_for(c, secs) is None
