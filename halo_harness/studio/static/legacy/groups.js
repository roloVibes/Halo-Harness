/* Halo Studio -- groups on the Roles and Org canvases (3.0.4.0 R6b). The
   owner: "rectangles to name the groups ... these are the researchers, these
   boxes go there, within them the cubes." A labelled rounded box is drawn
   BEHIND the cards of each group, the label at its top-left:
   - Roles: one box per role in the lineup (Main, Workers, Reviewers,
     Researchers, Judges, Custom roles ...; "Agents" when a card has none);
   - Org: one box per manager's reports ("<manager title>'s team", or the
     agent's metadata.team), the top level is "Leadership".
   Drag a box by its label strip to move the whole group; drop a card into
   another box to join it (Roles: the card takes that role; Org: it reports
   to that manager, after a confirm, the same PATCH as dropping onto the
   manager's card); a bio dragged from the rail into a box gets its role.
   `A` lays the groups out in rows; positions persist in the existing
   layout store (onMove). The toolbar's Groups button hides them
   (localStorage halo-studio-groups). */
(function () {
  "use strict";
  const svgNS = "http://www.w3.org/2000/svg";
  const PAD = 24, HEAD = 46, GX = 32, GY = 36, GAP = 60, MAXW = 1500, KEY = "halo-studio-groups";
  const ROLE_ORDER = ["main", "subagent", "researcher", "reviewer", "judge", "custom"];
  const ROLE_LABEL = { main: "Main", subagent: "Workers", researcher: "Researchers", reviewer: "Reviewers", judge: "Judges", custom: "Custom roles" };
  const mk = (tag, attrs, parent) => { const n = document.createElementNS(svgNS, tag); for (const k in attrs) n.setAttribute(k, attrs[k]); if (parent) parent.appendChild(n); return n; };
  const size = () => ({ W: window.HaloCanvas.W, H: window.HaloCanvas.H });
  const mode = () => (document.body.dataset.mode === "org" ? "org" : document.body.dataset.mode === "design" ? "design" : "roles");
  let on = true; try { on = localStorage.getItem(KEY) !== "off"; } catch (e) {}

  const roleLabel = (r) => ROLE_LABEL[r] || (r ? r.charAt(0).toUpperCase() + r.slice(1) + "s" : "Agents");
  function managerLabel(id, node) {  // the team's name, else "<manager>'s team": a short title, a chief's role, the name
    const a = window.orgMode && window.orgMode.agentById(id);
    const team = a && a.metadata && a.metadata.team;
    if (team) return String(team);
    const who = a && a.title && a.title.length <= 24 ? a.title : a && ["ceo", "cto", "cmo", "cfo", "pm"].includes(a.role) ? a.role.toUpperCase() : (a && a.name) || (node && node.agent) || "Manager";
    return `${who}'s team`;
  }

  /** The groups of the canvas's cards, ordered by tier (rows) then by the lineup / chart order. */
  function groupsOf(canvas) {
    if (!on || mode() === "design" || !canvas.nodes.length) return [];
    const out = new Map();
    const add = (key, label, tier, order, extra) => { if (!out.has(key)) out.set(key, Object.assign({ key, label, tier, order, members: [] }, extra)); return out.get(key); };
    if (mode() === "org") {
      const boss = {}; for (const e of canvas.edges) if (e.kind === "reports-to") boss[e.to] = e.from;
      const byId = Object.fromEntries(canvas.nodes.map((n) => [n.id, n]));
      const depth = (id) => { let d = 0, cur = boss[id]; const seen = new Set(); while (cur && byId[cur] && !seen.has(cur)) { seen.add(cur); d += 1; cur = boss[cur]; } return d; };
      for (const n of canvas.nodes) {
        const mid = boss[n.id] && byId[boss[n.id]] ? boss[n.id] : "";
        if (!mid) add("top", "Leadership", 0, 0, { manager: "" }).members.push(n);
        else add("m:" + mid, managerLabel(mid, byId[mid]), depth(mid) + 1, canvas.nodes.indexOf(byId[mid]), { manager: mid }).members.push(n);
      }
    } else {
      for (const n of canvas.nodes) {
        const r = n.role || "", i = ROLE_ORDER.indexOf(r);
        add("r:" + (r || "-"), roleLabel(r), r === "main" ? 0 : 1, i < 0 ? 50 : i, { role: r }).members.push(n);
      }
    }
    return [...out.values()].sort((a, b) => a.tier - b.tier || a.order - b.order || (a.label < b.label ? -1 : 1));
  }

  function box(g) {
    const { W, H } = size();
    const xs = g.members.map((n) => n.x), ys = g.members.map((n) => n.y);
    const x = Math.min(...xs) - PAD, y = Math.min(...ys) - HEAD;
    return { x, y, w: Math.max(...xs) + W + PAD - x, h: Math.max(...ys) + H + PAD - y };
  }
  const inside = (b, p) => p.x >= b.x && p.x <= b.x + b.w && p.y >= b.y && p.y <= b.y + b.h;
  const hits = (a, b) => a.x < b.x + b.w && b.x < a.x + a.w && a.y < b.y + b.h && b.y < a.y + a.h;

  /** The smallest box under a world point, leaving `except` (a card being dropped) out of every box. */
  function groupAt(canvas, p, except) {
    let best = null, area = Infinity;
    for (const g of groupsOf(canvas)) {
      const rest = { ...g, members: g.members.filter((n) => n !== except) };
      if (!rest.members.length) continue;
      const b = box(rest);
      if (inside(b, p) && b.w * b.h < area) { best = g; area = b.w * b.h; }
    }
    return best;
  }

  // -- drawing ----------------------------------------------------------------------
  let gdrag = null;
  function draw(canvas) {
    const layer = canvas.svg.querySelector("#groups"); if (!layer) return;
    layer.innerHTML = "";
    for (const g of groupsOf(canvas)) {
      const b = box(g);
      const el = mk("g", { class: "group", "data-testid": "canvas-group", "data-key": g.key, "data-tier": g.tier, "data-role": g.role || "" }, layer);
      mk("rect", { class: "group-box", x: b.x, y: b.y, width: b.w, height: b.h, rx: 18 }, el);
      const head = mk("g", { class: "group-head", transform: `translate(${b.x} ${b.y})` }, el);
      mk("title", {}, head).textContent = `${g.label}: drag this strip to move the group; drop a card in the box to join it`;
      mk("rect", { class: "group-handle", width: b.w, height: HEAD - 10, rx: 16 }, head);
      mk("text", { class: "group-label", x: 18, y: 24 }, head).textContent = g.label;
      mk("text", { class: "group-count", x: b.w - 18, y: 24, "text-anchor": "end" }, head).textContent = String(g.members.length);
      head.addEventListener("pointerdown", (ev) => {
        if (ev.button !== 0) return;
        ev.stopPropagation(); ev.preventDefault();
        const p = canvas.toWorld(ev.clientX, ev.clientY);
        gdrag = { canvas, px: p.x, py: p.y, members: g.members.map((n) => ({ n, x: n.x, y: n.y })), moved: false };
        canvas.svg.setPointerCapture(ev.pointerId); canvas.svg.classList.add("panning");
      });
    }
  }
  function bind(canvas) {
    const svg = canvas.svg;
    svg.addEventListener("pointermove", (ev) => {
      if (!gdrag || gdrag.canvas !== canvas) return;
      const p = canvas.toWorld(ev.clientX, ev.clientY);
      const dx = Math.round((p.x - gdrag.px) / 8) * 8, dy = Math.round((p.y - gdrag.py) / 8) * 8;
      for (const m of gdrag.members) { m.n.x = m.x + dx; m.n.y = m.y + dy; }
      gdrag.moved = gdrag.moved || !!dx || !!dy; canvas.render();
    });
    const up = () => {
      if (!gdrag || gdrag.canvas !== canvas) return;
      const d = gdrag; gdrag = null; svg.classList.remove("panning");
      if (d.moved) for (const m of d.members) canvas.onMove(m.n.id, m.n.x, m.n.y);
    };
    svg.addEventListener("pointerup", up); svg.addEventListener("pointercancel", up);
  }

  // -- auto-layout: the groups in rows (one row per tier, wrapping), each row centred --
  function layout(canvas) {
    const groups = groupsOf(canvas); if (!groups.length) return false;
    const { W, H } = size(); const rows = [];
    for (const g of groups) {
      const cols = Math.min(g.members.length, g.tier === 0 ? 4 : 3), lines = Math.ceil(g.members.length / cols);
      g.cols = cols; g.bw = PAD * 2 + cols * W + (cols - 1) * GX; g.bh = HEAD + lines * H + (lines - 1) * GY + PAD;
      let row = rows[rows.length - 1];
      if (!row || row.tier !== g.tier || row.w + GAP + g.bw > MAXW) rows.push((row = { tier: g.tier, w: -GAP, h: 0, groups: [] }));
      row.groups.push(g); row.w += GAP + g.bw; row.h = Math.max(row.h, g.bh);
    }
    const widest = Math.max(...rows.map((r) => r.w));
    let y = 60;
    for (const r of rows) {
      let x = 60 + (widest - r.w) / 2;
      for (const g of r.groups) {
        g.members.forEach((n, i) => { n.x = Math.round((x + PAD + (i % g.cols) * (W + GX)) / 8) * 8; n.y = Math.round((y + HEAD + Math.floor(i / g.cols) * (H + GY)) / 8) * 8; });
        x += g.bw + GAP;
      }
      y += r.h + GAP;
    }
    return true;
  }
  function overlapping(canvas) {
    const bs = groupsOf(canvas).map(box);
    return bs.some((a, i) => bs.some((b, j) => j > i && hits(a, b)));
  }

  function toggle(canvas) {
    on = !on; try { localStorage.setItem(KEY, on ? "on" : "off"); } catch (e) {}
    if (on && overlapping(canvas)) canvas.autoLayout(); else canvas.render();
    return on;
  }
  window.haloGroups = { draw, layout, groupsOf, groupAt, box, overlapping, toggle, on: () => on };

  // -- wiring into the page (app.js made window.app; this file loads after it) ---------
  const app = window.app; if (!app || !app.canvas) return;
  const canvas = app.canvas, C = window.HaloCanvas;
  bind(canvas);
  const bounds = C.prototype._bounds;  // fit and the minimap take the boxes in
  C.prototype._bounds = function () {
    const b = bounds.call(this), gs = groupsOf(this); if (!gs.length) return b;
    let x0 = b.x, y0 = b.y, x1 = b.x + b.w, y1 = b.y + b.h;
    for (const g of gs) { const q = box(g); x0 = Math.min(x0, q.x); y0 = Math.min(y0, q.y); x1 = Math.max(x1, q.x + q.w); y1 = Math.max(y1, q.y + q.h); }
    return { x: x0, y: y0, w: x1 - x0, h: y1 - y0 };
  };
  canvas.onDropIn = (node, p) => {
    if (!on || mode() === "design") return;
    const g = groupAt(canvas, p, node); if (!g || g.members.includes(node)) return;
    if (mode() === "org") joinTeam(node, g); else joinRole(node, g);
  };
  function joinRole(node, g) {
    const entry = app.current && app.current.raw.agents[node.index]; if (!entry) return;
    if (node.role === "main") { app.toast("Main stays main: drop another card onto it, or change the role in the Assignment tab", "warn"); return; }
    if (g.role === "main") { app.toast("A lineup has one main: drop the card onto the main card to make it report there", "warn"); return; }
    entry.role = g.role || "subagent";
    app.changed().then(() => app.toast(`${app.titleOf(entry)} joins ${g.label} (role: ${entry.role}). Save to keep it.`, "ok"));
  }
  function joinTeam(node, g) {
    const org = window.orgMode, a = org.agentById(node.id), boss = g.manager ? org.agentById(g.manager) : null;
    if (!a || a.id === g.manager || (a.reportsTo || "") === (g.manager || "")) { canvas.render(); return; }
    app.confirm(boss ? `${a.name} reports to ${boss.name}?` : `${a.name} joins Leadership?`,
      boss ? "This changes the reporting line in Paperclip (PATCH the agent's reportsTo)." : "It reports to nobody: the top of the company (PATCH the agent's reportsTo to none).", "", async () => {
        await api.pc("PATCH", `agents/${a.id}`, { reportsTo: boss ? boss.id : null });
        app.toast(boss ? `${a.name} now reports to ${boss.name}` : `${a.name} is in Leadership now`, "ok"); await org.refresh(app, true);
      });
  }
  const drop = canvas.onDrop;  // a bio from the rail dropped into a box takes that box's role
  canvas.onDrop = async (name, x, y) => {
    const { W, H } = size();
    const g = on && mode() === "roles" ? groupAt(canvas, { x: x + W / 2, y: y + H / 2 }) : null;
    const list0 = app.current && app.current.raw && app.current.raw.agents, before = list0 ? list0.length : -1;
    await drop(name, x, y);
    const list = app.current && app.current.raw && app.current.raw.agents;
    if (g && g.role && g.role !== "main" && list && list.length === before + 1 && list[before].role !== g.role) { list[before].role = g.role; await app.changed(); }
  };
  // a layout saved before the boxes existed can overlap them: lay the groups out once
  const select = app.selectLineup;
  app.selectLineup = async (name) => { await select(name); if (on && mode() === "roles" && overlapping(canvas)) canvas.autoLayout(); };
  if (window.orgMode) {
    const odraw = window.orgMode.draw;
    window.orgMode.draw = async (a, full) => { await odraw(a, full); if (full && on && mode() === "org" && overlapping(canvas)) canvas.autoLayout(); };
  }
  const btn = document.getElementById("btn-groups");
  const paint = () => { if (btn) { btn.classList.toggle("on", on); btn.setAttribute("aria-pressed", String(on)); } };
  if (btn) btn.addEventListener("click", () => { toggle(canvas); paint(); });
  paint();
})();
