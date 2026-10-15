/* Halo Studio -- Live Roles (3.0.5.0 R3). Framed in the shell (embedded=1),
   the Roles and Org canvases light up with the agents that run right now.
   The shell posts {type: "fleet-live", agents, pinned} on every change
   (routes/fleet/frames.ts); each live agent is matched to the card of the
   role or bio it runs under (Roles: its alias, bio, then role; Org: the
   position's title or name, or its Halo bio), and the card gets the glow in
   its band colour by what the agent does now (live.css): typing = a steady
   flow, a tool call = one pulse per call and the tool on the card, waiting
   = an amber pulse and the gate's diamond, done = one sweep, failed = a
   flash; a count badge when several agents share the card, a cost ticker.
   A spawn lights the line from the parent's card for a few seconds (D13).
   The Inspector gains a Live tab (live-tab.js), opened by itself when the
   selected card has a live agent. J / K hop between the working cards (and
   between the agents of one card), with the Live tab open F follows, Space
   pins its mini stream, P pauses; Esc unpins. The page never calls the
   fleet routes: it asks the shell (fleet-watch, fleet-command,
   fleet-history, fleet-pin) and the shell proxies them. R4: while a canvas
   replay runs (replay.js) the shell's fleet-live messages wait aside. */
(function () {
  "use strict";
  if (!/[?&]embedded=1\b/.test(location.search)) return;
  const app = window.app; if (!app || !app.canvas) return;
  const $ = (id) => document.getElementById(id);
  const esc = window.inspector.esc;
  const svgNS = "http://www.w3.org/2000/svg";
  const LIVE = ["queued", "running", "waiting", "paused"];
  const RANK = { failed: 7, waiting: 6, tool: 5, typing: 4, working: 4, done: 3, queued: 1 };
  const LABEL = { typing: "typing", working: "working", waiting: "waits on you", done: "done", failed: "failed", queued: "queued" };
  const GLYPH = [[/^(Edit|Write|MultiEdit|NotebookEdit)/, "✎"], [/^(Bash|PowerShell|Shell)/, "›_"], [/^(Read|Glob|LS)/, "▤"], [/^(Grep|Search)/, "⌕"], [/^(Agent|Task|SendMessage)/, "◉"], [/^Web/, "◍"]];
  const live = window.haloLive = { agents: [], byNode: {}, ready: false, watched: "", tabOpen: false, card: "", pinned: "", follow: true, sub: "thinking", stream: null, pending: {}, seq: 0 };
  const post = (msg) => { try { if (window.parent !== window) window.parent.postMessage(msg, location.origin); } catch (e) {} };
  live.post = post;
  live.isLive = (a) => LIVE.includes(a.state);
  live.ask = (msg) => new Promise((resolve) => {
    const id = ++live.seq; live.pending[id] = resolve; post({ ...msg, id });
    setTimeout(() => { if (live.pending[id]) { delete live.pending[id]; resolve({ ok: false, error: "Studio did not answer" }); } }, 20000);
  });
  const norm = (s) => String(s || "").trim().toLowerCase();
  const mode = () => document.body.dataset.mode || "roles";
  live.glyph = (tool) => { for (const [re, g] of GLYPH) if (re.test(tool)) return g; return "•"; };

  // -- which card an agent runs under ---------------------------------------------------------
  function matchNode(a, nodes) {
    if (mode() === "org") {
      return nodes.find((n) => {
        const pc = window.orgMode && window.orgMode.agentById(n.id); const meta = (pc && pc.metadata) || {};
        return [pc && pc.title, pc && pc.name, n.agent].some((t) => t && (norm(t) === norm(a.role) || norm(t) === norm(a.name))) || (meta.halo_agent && norm(meta.halo_agent) === norm(a.bio));
      }) || null;
    }
    const lineup = app.current && app.current.name;
    if (a.lineup && lineup && norm(a.lineup) !== norm(lineup)) return null;
    const role = (r) => nodes.filter((n) => norm(n.role) === norm(r));
    return nodes.find((n) => a.role && n.alias && norm(n.alias) === norm(a.role))
      || nodes.find((n) => a.bio && norm(n.agent) === norm(a.bio))
      || (a.role && role(a.role).length === 1 ? role(a.role)[0] : null)
      || (!a.parent ? nodes.find((n) => n.role === "main") || null : null);
  }
  function rematch() {
    live.byNode = {};
    if (mode() === "design") return;
    for (const a of live.agents) { const n = matchNode(a, app.canvas.nodes); if (n) (live.byNode[n.id] = live.byNode[n.id] || []).push(a); }
  }
  live.cardActivity = (list) => list.reduce((best, a) => ((RANK[a.activity] || 0) > (RANK[best] || 0) ? a.activity : best), "");

  // -- the glow, the badge, the spawn lines ------------------------------------------------------
  function edgeLayer(canvas) {
    let g = canvas.svg.querySelector("#live-edges");
    if (!g) { g = document.createElementNS(svgNS, "g"); g.id = "live-edges"; canvas.gEdges.after(g); }
    return g;
  }
  function spawnLines(canvas) {
    const layer = edgeLayer(canvas); layer.innerHTML = "";
    const W = window.HaloCanvas.W, H = window.HaloCanvas.H, now = Date.now() / 1000;
    const cardOf = {}; for (const [id, list] of Object.entries(live.byNode)) for (const a of list) cardOf[a.key] = id;
    for (const a of live.agents) {
      if (!a.parent || !a.since || now - a.since > 3) continue;
      const from = cardOf[a.key.split("|").slice(0, 2).join("|") + "|" + a.parent], to = cardOf[a.key];
      const p = from && canvas.node(from), q = to && canvas.node(to);
      if (!p || !q || p === q) continue;
      const x1 = p.x + W / 2, y1 = p.y + H, x2 = q.x + W / 2, y2 = q.y, dy = Math.max(40, Math.abs(y2 - y1) / 2);
      const path = document.createElementNS(svgNS, "path");
      path.setAttribute("d", `M${x1},${y1} C${x1},${y1 + dy} ${x2},${y2 - dy} ${x2},${y2}`); path.setAttribute("class", "edge live-spawn");
      path.setAttribute("data-testid", "live-spawn"); layer.appendChild(path);
    }
  }
  live.decorate = (canvas) => {
    if (!live.ready) return;
    rematch();  // a new lineup, a moved card, the Org chart refreshed: match again
    for (const g of canvas.gNodes.querySelectorAll(".node")) {
      const card = g.querySelector(".card"); if (!card) continue;
      card.querySelectorAll(".live-badge").forEach((b) => b.remove());
      const list = live.byNode[g.dataset.id] || [], act = live.cardActivity(list);
      if (!act) { delete g.dataset.live; g.removeAttribute("data-testid"); continue; }
      const lead = list.find((a) => a.activity === act) || list[0];
      g.dataset.live = act; g.dataset.pulse = (lead.calls || 0) % 2 ? "b" : "a"; g.setAttribute("data-testid", "live-card");
      const cost = list.reduce((s, a) => s + (Number(a.cost_usd) || 0), 0);
      const what = act === "tool" && lead.tool ? `<span class="live-tool" title="${esc(lead.current || lead.tool)}">${esc(live.glyph(lead.tool))} ${esc(lead.tool)}</span>`
        : act === "waiting" ? `<span class="live-diamond" title="waits on you">◆</span>` : `<span class="live-state">${esc(LABEL[act] || act)}</span>`;
      const badge = document.createElement("div"); badge.className = "live-badge";
      badge.innerHTML = `${what}${list.length > 1 ? `<span class="live-count" title="${list.length} agents on this card">×${list.length}</span>` : ""}<span class="live-cost">$${cost.toFixed(4)}</span>`;
      card.appendChild(badge);
    }
    spawnLines(canvas);
  };

  // -- the Live tab -------------------------------------------------------------------------------
  function ensureTab() {
    const tabs = document.querySelector("#inspector .tabs");
    if (!tabs || mode() === "design" || tabs.querySelector('[data-tab="live"]')) return;
    const b = document.createElement("button"); b.dataset.tab = "live"; b.setAttribute("data-testid", "live-tab"); b.textContent = "Live";
    b.title = "What the agents on this card do right now: their streams, Steer, Pause, Stop";
    b.addEventListener("click", () => live.open());
    tabs.appendChild(b);
    if (live.tabOpen) b.classList.add("on");
  }
  const selectedCard = () => (mode() === "org" ? (window.orgMode.selected && window.orgMode.selected.id) || "" : app.selected[0] || "");
  function watch(key) { if (live.watched !== key) { live.watched = key; live.stream = null; post({ type: "fleet-watch", key }); } }
  live.watch = (key) => { watch(key); if (live.tabOpen) window.haloLiveTab.render($("inspector-body")); };
  live.open = (cardId) => {
    live.tabOpen = true; live.card = cardId !== undefined ? cardId : selectedCard();
    document.querySelectorAll("#inspector .tabs button").forEach((x) => x.classList.toggle("on", x.dataset.tab === "live"));
    const list = live.byNode[live.card] || [];
    if (!list.some((a) => a.key === live.watched)) watch(list.length ? (list.find(live.isLive) || list[0]).key : "");
    window.haloLiveTab.render($("inspector-body"));
  };
  const show = app.showTab;  // any other tab closes the Live view
  app.showTab = (tab) => { live.tabOpen = false; return show(tab); };
  if (window.orgMode) { const oshow = window.orgMode.showTab; window.orgMode.showTab = (tab) => { live.tabOpen = false; return oshow(tab); }; }
  const onSelect = app.canvas.onSelect;  // a card with a live agent opens its Live tab
  app.canvas.onSelect = (ids) => {
    const id = ids[0] || "", goLive = live.ready && ((id && (live.byNode[id] || []).length) || live.tabOpen);
    if (goLive && mode() !== "org") { app.selected = ids; app.bioName = null; live.open(id); return; }
    onSelect(ids);
    if (goLive) live.open(id);
  };

  // -- hop: J / K across the working cards, and across the agents of one card ----------------------------
  function reveal(id) {
    const n = app.canvas.node(id), c = app.canvas, r = c.svg.getBoundingClientRect(); if (!n) return;
    const sx = c.t.x + n.x * c.t.k, sy = c.t.y + n.y * c.t.k, W = window.HaloCanvas.W * c.t.k, H = window.HaloCanvas.H * c.t.k;
    if (sx >= 0 && sy >= 0 && sx + W <= r.width && sy + H <= r.height) return;
    c.t.x = r.width / 2 - (n.x + window.HaloCanvas.W / 2) * c.t.k; c.t.y = r.height / 2 - (n.y + window.HaloCanvas.H / 2) * c.t.k; c._apply();
  }
  function hop(dir) {
    const working = (id) => (live.byNode[id] || []).filter(live.isLive);
    const here = working(live.card), i = here.findIndex((a) => a.key === live.watched);
    if (live.tabOpen && here.length > 1 && i >= 0 && i + dir >= 0 && i + dir < here.length) { live.watch(here[i + dir].key); return; }
    const order = app.canvas.nodes.map((n) => n.id).filter((id) => working(id).length);
    if (!order.length) return;
    const ci = order.indexOf(live.card);
    const next = order[ci < 0 ? (dir > 0 ? 0 : order.length - 1) : (ci + dir + order.length) % order.length];
    const list = working(next);
    watch(dir > 0 ? list[0].key : list[list.length - 1].key);
    app.canvas.select([next]); reveal(next);
  }
  live.hop = hop;
  /** Pin (or unpin, "") a stream: the shell keeps the mini stream; this page knows at once, not at the next fleet-live. */
  live.pin = (key) => { live.pinned = key; post({ type: "fleet-pin", key }); if (live.tabOpen) window.haloLiveTab.refresh(); };
  window.addEventListener("keydown", (ev) => {
    if (!live.ready || ev.ctrlKey || ev.metaKey || ev.altKey || /^(INPUT|TEXTAREA|SELECT)$/.test((document.activeElement || {}).tagName || "")) return;
    const k = ev.key.length === 1 ? ev.key.toLowerCase() : ev.key, tab = window.haloLiveTab;
    if (k === "j" || k === "k") hop(k === "j" ? 1 : -1);
    else if (live.tabOpen && k === "f") tab.toggleFollow();
    else if (live.tabOpen && k === " " && live.watched) live.pin(live.pinned === live.watched ? "" : live.watched);
    else if (live.tabOpen && k === "p" && live.watched) tab.command("pause");
    else if (k === "Escape" && live.pinned) live.pin("");
    else return;
    ev.preventDefault(); ev.stopImmediatePropagation();
  }, true);

  // -- the shell's messages ---------------------------------------------------------------------------
  window.addEventListener("message", (e) => {
    if (e.origin !== location.origin || e.source !== window.parent || !e.data || typeof e.data !== "object") return;
    const d = e.data;
    if (d.type === "fleet-live") {
      if (live.replaying) { live.held = d; return; }  // a replay runs (replay.js): what runs now waits until it closes
      live.ready = true; live.agents = Array.isArray(d.agents) ? d.agents : []; live.pinned = d.pinned || "";
      live.decorate(app.canvas); ensureTab();
      if (live.tabOpen) window.haloLiveTab.refresh();
    } else if (d.type === "fleet-stream") {
      if (d.key === live.watched) { live.stream = d; window.haloLiveTab.stream(d); }
    } else if (d.type === "fleet-result") {
      const fn = live.pending[d.id]; if (fn) { delete live.pending[d.id]; fn(d); }
    } else if (d.type === "fleet-hop") hop(d.dir > 0 ? 1 : -1);
  });
  const tabs = document.querySelector("#inspector .tabs");  // Roles / Org rebuild the tab row: the Live tab comes back
  if (tabs) new MutationObserver(() => live.ready && ensureTab()).observe(tabs, { childList: true });
  post({ type: "fleet-ready" });
})();
