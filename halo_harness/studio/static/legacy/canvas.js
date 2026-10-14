/* Halo Studio -- the SVG canvas: pan, zoom, a dot grid, node cards in
   foreignObjects, bezier edges with labels, drag with snap, marquee
   multi-select, a minimap, fit and a layered auto-layout. Pure view: it
   emits onSelect / onMove / onDrop / onOpen and never touches the API.
   3.0.4.0 R6b: window.haloGroups (groups.js) draws the labelled group boxes
   behind the cards, lays the groups out in rows (`A`), and gets a card
   dropped into another box (onDropIn). */
(function () {
  "use strict";
  const W = 236, H = 112, SNAP = 8;
  const svgNS = "http://www.w3.org/2000/svg";
  const el = (tag, attrs, parent) => { const n = document.createElementNS(svgNS, tag); for (const k in attrs || {}) n.setAttribute(k, attrs[k]); if (parent) parent.appendChild(n); return n; };
  const esc = (s) => String(s == null ? "" : s).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));

  class Canvas {
    constructor(svg, minimap) {
      this.svg = svg; this.minimap = minimap; this.world = svg.querySelector("#world");
      this.gEdges = svg.querySelector("#edges"); this.gNodes = svg.querySelector("#nodes"); this.marquee = svg.querySelector("#marquee");
      this.nodes = []; this.edges = []; this.selected = new Set(); this.live = {};
      this.t = { x: 80, y: 80, k: 1 }; this.onSelect = () => {}; this.onMove = () => {}; this.onDrop = () => {}; this.onOpen = () => {}; this.onDropOn = null; this.onDropIn = null;
      this._bind();
    }
    setGraph(nodes, edges, positions) {
      const old = Object.fromEntries(this.nodes.map((n) => [n.id, n]));
      this.nodes = nodes.map((n, i) => ({ ...n, x: (positions && positions[n.id] && positions[n.id].x) ?? old[n.id]?.x ?? 80 + (i % 3) * 320, y: (positions && positions[n.id] && positions[n.id].y) ?? old[n.id]?.y ?? 60 + Math.floor(i / 3) * 170 }));
      this.edges = edges; this.selected = new Set([...this.selected].filter((id) => old[id] && this.nodes.some((n) => n.id === id)));
      if (!positions || !Object.keys(positions).length) this.autoLayout(false);
      this.render();
    }
    positions() { return Object.fromEntries(this.nodes.map((n) => [n.id, { x: n.x, y: n.y }])); }
    nodeAt(x, y, except = []) { return this.nodes.find((n) => !except.includes(n.id) && x >= n.x && x <= n.x + W && y >= n.y && y <= n.y + H) || null; }
    node(id) { return this.nodes.find((n) => n.id === id); }
    setLive(live) { this.live = live || {}; this.render(); }
    select(ids, additive) { if (!additive) this.selected.clear(); for (const id of ids) this.selected.add(id); this.render(); this.onSelect([...this.selected]); }

    // -- geometry ---------------------------------------------------------
    toWorld(cx, cy) { const r = this.svg.getBoundingClientRect(); return { x: (cx - r.left - this.t.x) / this.t.k, y: (cy - r.top - this.t.y) / this.t.k }; }
    _apply() { this.world.setAttribute("transform", `translate(${this.t.x} ${this.t.y}) scale(${this.t.k})`); this._minimap(); }
    zoomBy(f, cx, cy) {
      const r = this.svg.getBoundingClientRect(); const px = cx == null ? r.width / 2 : cx - r.left, py = cy == null ? r.height / 2 : cy - r.top;
      const k = Math.min(2.5, Math.max(0.2, this.t.k * f)); this.t.x = px - (px - this.t.x) * (k / this.t.k); this.t.y = py - (py - this.t.y) * (k / this.t.k); this.t.k = k; this._apply();
    }
    zoomTo(k) { const r = this.svg.getBoundingClientRect(); this.zoomBy(k / this.t.k, r.left + r.width / 2, r.top + r.height / 2); }
    fit() {
      if (!this.nodes.length) return; const r = this.svg.getBoundingClientRect(); const b = this._bounds();
      const pad = { x: 80, top: 40, bottom: 150 };  // the zoom pill, the minimap and the timeline live along the bottom
      const k = Math.min(2, Math.max(0.2, Math.min((r.width - pad.x) / (b.w || 1), (r.height - pad.top - pad.bottom) / (b.h || 1))));
      this.t = { k, x: (r.width - b.w * k) / 2 - b.x * k, y: pad.top + (r.height - pad.top - pad.bottom - b.h * k) / 2 - b.y * k }; this._apply();
    }
    _bounds() { const xs = this.nodes.map((n) => n.x), ys = this.nodes.map((n) => n.y); const x = Math.min(...xs), y = Math.min(...ys); return { x, y, w: Math.max(...xs) + W - x, h: Math.max(...ys) + H - y }; }
    autoLayout(render = true) {
      if (!(window.haloGroups && window.haloGroups.layout(this))) this._layered();
      if (render) { this.render(); this.fit(); for (const n of this.nodes) this.onMove(n.id, n.x, n.y, true); }
    }
    _layered() {
      const layer = {}; const inc = {};
      for (const e of this.edges) if (e.kind !== "pipeline") (inc[e.to] = inc[e.to] || []).push(e.from);
      const roots = this.nodes.filter((n) => n.role === "main" || !(inc[n.id] || []).length).map((n) => n.id);
      const queue = roots.map((id) => [id, 0]); const seen = new Set();
      while (queue.length) { const [id, d] = queue.shift(); if (seen.has(id)) continue; seen.add(id); layer[id] = Math.max(layer[id] || 0, d); for (const e of this.edges) if (e.from === id && e.kind !== "pipeline" && !seen.has(e.to)) queue.push([e.to, d + 1]); }
      for (const n of this.nodes) if (layer[n.id] == null) layer[n.id] = 1;
      const cols = {}; for (const n of this.nodes) (cols[layer[n.id]] = cols[layer[n.id]] || []).push(n);
      const maxRows = Math.max(...Object.values(cols).map((c) => c.length));
      for (const [l, list] of Object.entries(cols)) list.forEach((n, i) => { n.x = 60 + Number(l) * 330; n.y = 60 + i * 150 + ((maxRows - list.length) * 150) / 2; });
    }

    // -- render -------------------------------------------------------------
    render() {
      this.gEdges.innerHTML = ""; this.gNodes.innerHTML = "";
      if (window.haloGroups) window.haloGroups.draw(this);
      const pos = Object.fromEntries(this.nodes.map((n) => [n.id, n]));
      for (const e of this.edges) {
        const a = pos[e.from], b = pos[e.to]; if (!a || !b) continue;
        let x1 = a.x + W, y1 = a.y + H / 2, x2 = b.x, y2 = b.y + H / 2, d;
        if (Math.abs(b.x - a.x) < W / 2) {  // same column: leave from the bottom (or top), arrive at the top (or bottom)
          const down = b.y >= a.y; x1 = a.x + W / 2; x2 = b.x + W / 2; y1 = down ? a.y + H : a.y; y2 = down ? b.y : b.y + H;
          const dy = Math.max(40, Math.abs(y2 - y1) / 2) * (down ? 1 : -1);
          d = `M${x1},${y1} C${x1},${y1 + dy} ${x2},${y2 - dy} ${x2},${y2}`;
        } else if (b.x < a.x) {  // backwards: leave from the left edge, arrive at the right edge
          x1 = a.x; x2 = b.x + W; const dx = Math.max(60, Math.abs(x2 - x1) / 2);
          d = `M${x1},${y1} C${x1 - dx},${y1} ${x2 + dx},${y2} ${x2},${y2}`;
        } else {
          const dx = Math.max(60, Math.abs(x2 - x1) / 2);
          d = `M${x1},${y1} C${x1 + dx},${y1} ${x2 - dx},${y2} ${x2},${y2}`;
        }
        const liveEdge = this.live[e.to] && this.live[e.to].state === "running";
        const p = el("path", { d, class: `edge ${e.kind}${liveEdge ? " live" : ""}`, "marker-end": "url(#arrow)" }, this.gEdges);
        p.addEventListener("click", (ev) => { ev.stopPropagation(); this.select([e.to]); });
        const vertical = Math.abs(b.x - a.x) < W / 2;
        if (e.label) el("text", { x: vertical ? x1 + 10 : (x1 + x2) / 2, y: (y1 + y2) / 2 + (vertical ? 4 : -6), "text-anchor": vertical ? "start" : "middle", class: "edge-label" }, this.gEdges).textContent = e.label;
      }
      for (const n of this.nodes) {
        const live = this.live[n.id];
        const g = el("g", { class: `node${this.selected.has(n.id) ? " selected" : ""}${live ? " live" : ""}${n.justDropped ? " dropped" : ""}`, transform: `translate(${n.x} ${n.y})`, "data-role": n.role, "data-kind": n.kind || "lineup", "data-id": n.id, tabindex: 0, role: "button", "aria-label": `${n.agent}, ${n.role}` }, this.gNodes);
        const fo = el("foreignObject", { width: W, height: H + 40 }, g);
        const status = n.statusClass || (n.problems?.length ? "bad" : n.warnings?.length ? "warn" : live?.state === "running" ? "running" : "");
        const title = (n.problems || []).concat(n.warnings || []).join("\n");
        fo.innerHTML = `<div xmlns="http://www.w3.org/1999/xhtml" class="card" style="position:relative" title="${esc(title)}">
          <div class="band"></div>
          <div class="head"><span class="agent">${esc(n.agent)}</span>${n.scope === "template" ? '<span class="lock" title="This agent bio ships with Halo and is read-only. Click here (or open the Agent tab) and press Duplicate to get an editable copy in your scope.">🔒 shipped</span>' : ""}</div>
          <div class="role">${n.subtitle != null ? esc(n.subtitle) : esc(n.role) + (n.alias && n.alias !== n.role ? " · as " + esc(n.alias) : "") + (n.instances > 1 ? " · ×" + n.instances : "")}</div>
          <div class="model" title="${esc(n.chip || n.model || "no model")}"><span>${esc(n.chip || n.model || "no model resolves")}</span></div>
          <div class="meta">${n.metaHtml != null ? n.metaHtml : (n.price && n.price !== "?" ? `<span><b>${esc(n.price)}</b></span>` : `<span>price ?</span>`) + (n.context ? `<span>ctx <b>${esc(n.context)}</b></span>` : "") + (n.tools != null ? `<span>tools <b>${n.tools}</b></span>` : "")}</div>
          <div class="run">${live ? esc(`${live.state}${live.cost ? " · $" + live.cost : ""}${live.turns ? " · " + live.turns + " turns" : ""}`) : ""}</div>
          <span class="status ${status}"></span></div>`;
        n.justDropped = false;
        const lock = fo.querySelector(".lock");  // 3.0.2.0: the lock is a badge, not a toggle -- say so
        if (lock) lock.addEventListener("pointerdown", (ev) => { ev.stopPropagation(); this.select([n.id]); if (this.onLock) this.onLock(n.id); });
        g.addEventListener("pointerdown", (ev) => this._nodeDown(ev, n));
        g.addEventListener("dblclick", (ev) => { ev.stopPropagation(); this.onOpen(n.id); });
        g.addEventListener("keydown", (ev) => { if (ev.key === "Enter") this.onOpen(n.id); });
      }
      this._apply();
    }
    _minimap() {
      if (!this.minimap) return; this.minimap.innerHTML = ""; if (!this.nodes.length) return;
      const b = this._bounds(); const r = this.svg.getBoundingClientRect(); const vx = -this.t.x / this.t.k, vy = -this.t.y / this.t.k, vw = r.width / this.t.k, vh = r.height / this.t.k;
      const minX = Math.min(b.x, vx), minY = Math.min(b.y, vy), maxX = Math.max(b.x + b.w, vx + vw), maxY = Math.max(b.y + b.h, vy + vh);
      const s = Math.min(170 / (maxX - minX), 100 / (maxY - minY)); const ox = 5 - minX * s, oy = 5 - minY * s;
      for (const n of this.nodes) el("rect", { x: ox + n.x * s, y: oy + n.y * s, width: W * s, height: H * s, rx: 2, fill: `var(--role-${["main", "subagent", "reviewer", "researcher", "judge"].includes(n.role) ? n.role : "custom"})`, opacity: .8 }, this.minimap);
      el("rect", { class: "view", x: ox + vx * s, y: oy + vy * s, width: vw * s, height: vh * s, rx: 2 }, this.minimap);
    }

    // -- interaction ------------------------------------------------------------
    _bind() {
      const svg = this.svg; let pan = null, drag = null, box = null;
      svg.addEventListener("wheel", (ev) => { ev.preventDefault(); if (ev.ctrlKey || ev.metaKey || !ev.shiftKey) this.zoomBy(ev.deltaY < 0 ? 1.1 : 0.9, ev.clientX, ev.clientY); else { this.t.x -= ev.deltaY; this._apply(); } }, { passive: false });
      svg.addEventListener("pointerdown", (ev) => {
        if (ev.target.closest(".node")) return;
        if (ev.shiftKey) { box = { start: this.toWorld(ev.clientX, ev.clientY) }; this.marquee.style.display = ""; }
        else { pan = { x: ev.clientX - this.t.x, y: ev.clientY - this.t.y }; svg.classList.add("panning"); if (!ev.ctrlKey) this.select([]); }
        svg.setPointerCapture(ev.pointerId);
      });
      svg.addEventListener("pointermove", (ev) => {
        if (pan) { this.t.x = ev.clientX - pan.x; this.t.y = ev.clientY - pan.y; this._apply(); }
        else if (drag) { const p = this.toWorld(ev.clientX, ev.clientY); const dx = Math.round((p.x - drag.px) / SNAP) * SNAP, dy = Math.round((p.y - drag.py) / SNAP) * SNAP; for (const n of drag.nodes) { n.x = n.ox + dx; n.y = n.oy + dy; } drag.moved = drag.moved || dx || dy; this.render(); }
        else if (box) { const p = this.toWorld(ev.clientX, ev.clientY); const x = Math.min(p.x, box.start.x), y = Math.min(p.y, box.start.y), w = Math.abs(p.x - box.start.x), h = Math.abs(p.y - box.start.y); box.rect = { x, y, w, h }; Object.entries({ x, y, width: w, height: h }).forEach(([k, v]) => this.marquee.setAttribute(k, v)); }
      });
      const up = (ev) => {
        if (pan) { pan = null; svg.classList.remove("panning"); }
        if (drag) {
          if (drag.moved) {
            const p = this.toWorld(ev.clientX, ev.clientY); const over = drag.nodes.length === 1 ? this.nodeAt(p.x, p.y, [drag.nodes[0].id]) : null;
            if (over && this.onDropOn) this.onDropOn(drag.nodes[0].id, over.id, drag.nodes[0]);
            else { for (const n of drag.nodes) this.onMove(n.id, n.x, n.y); if (drag.nodes.length === 1 && this.onDropIn) this.onDropIn(drag.nodes[0], p); }  // into another group box
          }
          else this.select([drag.nodes[0].id], ev.ctrlKey || ev.metaKey);
          for (const n of drag.nodes) n.dragging = false; drag = null; this.render();
        }
        if (box) { const r = box.rect; if (r) this.select(this.nodes.filter((n) => n.x + W > r.x && n.x < r.x + r.w && n.y + H > r.y && n.y < r.y + r.h).map((n) => n.id), ev.ctrlKey); this.marquee.style.display = "none"; this.marquee.setAttribute("width", 0); box = null; }
      };
      svg.addEventListener("pointerup", up); svg.addEventListener("pointercancel", up);
      this._nodeDown = (ev, n) => {
        ev.stopPropagation(); if (ev.button !== 0) return;
        const ids = this.selected.has(n.id) ? [...this.selected] : [n.id]; const p = this.toWorld(ev.clientX, ev.clientY);
        drag = { px: p.x, py: p.y, nodes: ids.map((id) => this.node(id)).filter(Boolean).map((m) => Object.assign(m, { ox: m.x, oy: m.y })), moved: false };
        svg.setPointerCapture(ev.pointerId);
      };
      svg.addEventListener("dragover", (ev) => { ev.preventDefault(); ev.dataTransfer.dropEffect = "copy"; });
      svg.addEventListener("drop", (ev) => { ev.preventDefault(); const name = ev.dataTransfer.getData("text/halo-bio") || ev.dataTransfer.getData("text/plain"); if (!name) return; const p = this.toWorld(ev.clientX, ev.clientY); this.onDrop(name, Math.round((p.x - W / 2) / SNAP) * SNAP, Math.round((p.y - H / 2) / SNAP) * SNAP); });
      new ResizeObserver(() => this._apply()).observe(svg);
    }
  }
  Canvas.W = W; Canvas.H = H;  // the card size, for groups.js
  window.HaloCanvas = Canvas;
})();
