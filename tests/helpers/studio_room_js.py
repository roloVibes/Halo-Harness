"""tests.helpers.studio_room_js -- what the room driver (tests/helpers/studio_room.py, Halo 3.6.0.0 R0a) runs in the page.
Started from the audit's room walk (its per-panel measure: sideways scrollbars, cut text, text under 12 px, low or
crowded controls, overlaps), reshaped for the stage: one record for the view (R1 the main thing's share, R3 the strips
and the stage height) and one per region (the main thing, each open drawer, or the page of a paged section)."""

# the R7 measure leaves out a link inside a line of text (`.og-link`, `.link-btn`: a word, not a control)
# boxes that pan by design (R4's named exemptions): a canvas, a map, a drawing, a code or log block
CANVASES = ("[data-testid=roles-canvas]", "[data-testid=roles-live-map]", "[data-testid=session-map]", ".cz-world", ".cz-viewport",
            "svg", "pre", "code", "textarea", "[data-pan]", ".lv-world", ".pw-world", "[data-testid=live-plan]")

MEASURE = r"""((exempt) => {
  const vis = (el) => { const r = el.getBoundingClientRect(); return r.width > 1 && r.height > 1 && getComputedStyle(el).visibility !== 'hidden' && !el.closest('[hidden]'); };
  const view = [...document.querySelectorAll('.section-view')].find(vis);
  if (!view) return null;
  const R = (el) => { const r = el.getBoundingClientRect(); return [Math.round(r.left), Math.round(r.top), Math.round(r.width), Math.round(r.height)]; };
  const ws = [...view.querySelectorAll('.workspace')].find((w) => vis(w) && w.querySelector('.stage-main'));
  const stage = ws && ws.querySelector('.stage-row');
  const main = ws && ws.querySelector('.stage-main');
  const drawers = ws ? [...ws.querySelectorAll('.stage-drawer')].filter(vis) : [];
  const page = view.querySelector('.lc-scroll, [data-testid=setup-page], [data-testid=settings-page], .st-page, .sp-page') || view;
  const regions = ws ? [main, ...drawers] : [page];
  const isExempt = (e) => exempt.some((s) => e.matches(s) || e.closest(s));
  const INLINE = '.og-link, .link-btn';
  const leaves = (root) => [...root.querySelectorAll('*')].filter((e) => vis(e) && [...e.childNodes].some((n) => n.nodeType === 3 && n.textContent.trim()));
  const one = (root) => {
    const all = [...root.querySelectorAll('*')].filter(vis);
    const hs = all.filter((e) => /(auto|scroll)/.test(getComputedStyle(e).overflowX) && e.scrollWidth > e.clientWidth + 2 && !isExempt(e));
    const lv = leaves(root);
    const cut = lv.filter((e) => e.scrollWidth > e.clientWidth + 1 && /(hidden|clip)/.test(getComputedStyle(e).overflowX) && !isExempt(e));
    const bare = cut.filter((e) => !e.closest('[title], [data-hover], [aria-label]'));
    const small = lv.filter((e) => parseFloat(getComputedStyle(e).fontSize) < 12);
    const ctl = all.filter((e) => e.matches('button, select, input:not([type=checkbox]):not([type=radio]):not([type=range]), [role=button], summary') && !isExempt(e));
    const low = ctl.filter((e) => e.getBoundingClientRect().height < 27.5 && !e.matches(INLINE));  // a link inside a line of text is a word, not a control
    const rs = ctl.map((e) => e.getBoundingClientRect());
    let close = 0, overlap = 0; const over = [];
    for (let i = 0; i < rs.length && i < 200; i++) for (let j = i + 1; j < rs.length && j < 200; j++) {
      const a = rs[i], b = rs[j];
      if (ctl[i].contains(ctl[j]) || ctl[j].contains(ctl[i])) continue;
      const ix = Math.min(a.right, b.right) - Math.max(a.left, b.left), iy = Math.min(a.bottom, b.bottom) - Math.max(a.top, b.top);
      if (ix > 1 && iy > 1) { overlap++; over.push(ctl[i].dataset.testid || ctl[i].className || ctl[i].tagName); continue; }
      const sameRow = iy > Math.min(a.height, b.height) / 2, sameCol = ix > Math.min(a.width, b.width) / 2;
      const gx = Math.max(a.left, b.left) - Math.min(a.right, b.right), gy = Math.max(a.top, b.top) - Math.min(a.bottom, b.bottom);
      if ((sameRow && gx >= 0 && gx < 7.5) || (sameCol && gy >= 0 && gy < 7.5)) close++;
    }
    const nm = (e) => String(e.dataset.testid || e.className || e.tagName).slice(0, 40);
    return {id: root.dataset.panelIn || root.querySelector('.ws-cell')?.dataset.panel || 'page', rect: R(root), cw: +(root.dataset.contentW || 0),
            hscroll: hs.map(nm).slice(0, 4), cut: cut.length, bare: bare.map((e) => e.innerText.slice(0, 30)).slice(0, 3),
            small: small.length, small_ex: [...new Set(small.map((e) => getComputedStyle(e).fontSize))].slice(0, 3),
            ctl: ctl.length, low: low.length, low_ex: low.map(nm).slice(0, 3), close, overlap, over: over.slice(0, 3)};
  };
  const H = (sel) => { const e = document.querySelector(sel); return e && vis(e) ? Math.round(e.getBoundingClientRect().height) : 0; };
  const bar = ws ? H('.section-view:not([hidden]) .viewbar') + [...view.querySelectorAll('.agents-bar, [data-testid=agents-bar]')].filter(vis).reduce((m, e) => m + Math.round(e.getBoundingClientRect().height), 0) : 0;
  const strips = [...document.querySelectorAll('.panel[data-collapsed], .ws-grid')].filter(vis).length;
  return {vw: innerWidth, vh: innerHeight, stage: stage ? R(stage) : R(view), main: main ? R(main) : null, view: R(view),
          header: H('.topbar'), status: H('.hud-strip'), bar, strips, doc_hscroll: document.documentElement.scrollWidth > innerWidth + 1,
          drawers: drawers.map((d) => [d.dataset.panelIn || '', d.dataset.side || '', Math.round(d.getBoundingClientRect().width), !!d.dataset.floating]),
          regions: regions.filter(Boolean).map(one)};
})"""

# the view bar's drawer buttons (data-role drawer), in order
DRAWER_BTNS = ("[...document.querySelectorAll('.section-view:not([hidden]) [data-testid=viewbar-btn][data-role=drawer]')]"
               ".filter((b) => b.getBoundingClientRect().width > 0).map((b) => b.dataset.panel)")


def btn(pid: str) -> str:
    return f"document.querySelector('.section-view:not([hidden]) [data-testid=viewbar-btn][data-panel=\"{pid}\"]')"


def drawn(pid: str) -> str:
    """The drawer `pid` is open and its panel's body drawn."""
    return f"!!document.querySelector('.section-view:not([hidden]) .stage-drawer[data-panel-in=\"{pid}\"] .panel-body')"
