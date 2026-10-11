/* Halo Studio -- the app: state, the rail, canvas wiring, the inspector
   tabs, validate / save / apply, the run view, toasts, shortcuts. */
(function () {
  "use strict";
  const { h, esc, problems } = window.inspector;
  const $ = (id) => document.getElementById(id);
  const app = window.app = {
    state: {}, lineups: [], bios: [], models: [], tools: [], current: null, dirty: false, scope: "user",
    selected: [], bioName: null, tab: "assignment", runView: false, live: {}, _runTimer: null,
  };
  app.canvas = new HaloCanvas($("canvas"), $("minimap"));
  app.palette = studioPalette(app);

  // -- helpers -------------------------------------------------------------------
  app.toast = (msg, kind = "") => { const t = h(`<div class="toast ${kind}">${esc(msg)}</div>`); $("toasts").appendChild(t); setTimeout(() => t.remove(), 4200); };
  app.confirm = (title, text, diff, onYes) => {
    const m = $("confirm"); $("confirm-title").textContent = title; $("confirm-text").textContent = text; $("confirm-diff").innerHTML = diff || ""; $("confirm-diff").style.display = diff ? "" : "none";
    m.classList.add("open"); $("confirm-yes").onclick = async () => { m.classList.remove("open"); try { await onYes(); } catch (e) { app.toast(e.message, "bad"); } }; $("confirm-no").onclick = () => m.classList.remove("open");
  };
  app.selectedNode = () => { const g = app.current && app.current.graph; const id = app.selected[0]; return g ? g.nodes.find((n) => n.id === id) : null; };
  const status = () => {
    const cur = app.current; const v = $("status-valid");
    if (!cur) { v.textContent = "no lineup"; v.className = ""; }
    else if (cur.problems && cur.problems.length) { v.textContent = `${cur.problems.length} problem(s)`; v.className = "bad"; }
    else { const warns = cur.graph.nodes.reduce((a, n) => a + (n.warnings || []).length + (n.problems || []).length, 0); v.textContent = warns ? `${warns} warning(s)` : "valid"; v.className = warns ? "warn" : "ok"; }
    $("status-active").textContent = app.state.active_team ? `active: ${app.state.active_team}` : "no active lineup (one model for everything)";
    $("status-dirty").textContent = app.dirty ? "unsaved changes" : "";
    $("status-url").textContent = location.host;
    $("btn-save").disabled = !cur; $("btn-apply").disabled = !cur || app.dirty; $("btn-validate").disabled = !cur;
    document.title = (app.dirty ? "• " : "") + (cur ? cur.name + " · " : "") + "Halo Studio";
  };

  // -- loading --------------------------------------------------------------------
  app.reloadLists = async () => {
    [app.lineups, app.bios] = await Promise.all([api.lineups(), api.bios()]);
    const sel = $("lineup-select"); sel.innerHTML = app.lineups.map((l) => `<option value="${esc(l.name)}"${app.current && l.name === app.current.name ? " selected" : ""}>${esc(l.name)}${l.active ? " ✓" : ""}</option>`).join("");
    $("lineup-list").innerHTML = app.lineups.map((l) => `<li data-name="${esc(l.name)}" class="${app.current && l.name === app.current.name ? "active" : ""}"><span class="name">${esc(l.name)}${l.active ? ' <span class="badge live">active</span>' : ""}</span><span class="badge ${esc(l.scope)}">${esc(l.scope === "template" ? "shipped" : l.scope)}</span><span class="desc">${esc(l.description || l.roles.join(", "))}</span></li>`).join("");
    $("bio-list").innerHTML = app.bios.map((b) => `<div class="bio-chip" draggable="true" data-name="${esc(b.name)}" title="${esc(b.description)}"><span class="dot" style="background:var(--role-${esc(["main", "subagent", "reviewer", "researcher", "judge"].includes(b.kind) ? b.kind : "custom")})"></span>${esc(b.name)}<span class="model">${esc(b.model || "")}</span></div>`).join("");
    $("starters").innerHTML = app.lineups.filter((l) => l.scope === "template").slice(0, 6).map((l) => `<button data-name="${esc(l.name)}"><b>${esc(l.name)}</b><small>${esc(l.description || l.roles.join(", "))}</small></button>`).join("");
  };
  app.selectLineup = async (name) => {
    if (app.dirty && app.current && app.current.name !== name && !window.confirm("Discard unsaved changes?")) return;
    app.current = await api.lineup(name); app.dirty = false; app.selected = []; app.bioName = null;
    app.canvas.setGraph(app.current.graph.nodes, app.current.graph.edges, app.current.layout);
    if (!app.current.layout || !Object.keys(app.current.layout).length) app.canvas.fit();
    $("canvas-empty").style.display = "none";
    $("lineup-badges").innerHTML = `<span class="badge ${esc(app.current.scope)}">${esc(app.current.scope === "template" ? "shipped: saving makes your copy" : app.current.scope)}</span>`;
    await app.reloadLists(); app.showTab(app.tab); status();
  };
  app.refreshGraph = async () => {
    if (!app.current) return;
    const r = await api.validate("lineup", app.current.raw, app.current.name);
    app.current.problems = r.problems; app.current.graph = r.graph;
    app.canvas.setGraph(r.graph.nodes, r.graph.edges, app.canvas.positions()); status();
  };
  app.changed = async () => { app.dirty = true; await app.refreshGraph(); if (app.tab !== "yaml") app.showTab(app.tab); else if (app.current._yamlBox) app.current._yamlBox.value = (await api.toYaml(app.current.raw)).yaml; };
  app.replaceRaw = async (raw) => { app.current.raw = raw; app.dirty = true; await app.refreshGraph(); };
  app.removeSelected = async () => { const n = app.selectedNode(); if (!n) return; app.current.raw.agents.splice(n.index, 1); app.selected = []; await app.changed(); };

  // -- tabs ----------------------------------------------------------------------
  app.showTab = async (tab) => {
    app.tab = tab; document.querySelectorAll("#inspector .tabs button").forEach((b) => b.classList.toggle("on", b.dataset.tab === tab));
    const body = $("inspector-body"); body.innerHTML = "";
    if (tab === "assignment") window.inspector.assignmentTab(body, app);
    else if (tab === "agent") await window.bioForm.render(body, app);
    else if (tab === "lineup") window.inspector.lineupTab(body, app);
    else window.inspector.yamlTab(body, app);
  };
  document.querySelectorAll("#inspector .tabs button").forEach((b) => b.addEventListener("click", () => app.showTab(b.dataset.tab)));

  // -- actions ---------------------------------------------------------------------
  app.validate = async () => { if (!app.current) return; await app.refreshGraph(); const n = (app.current.problems || []).length; app.toast(n ? `${n} problem(s): see the Lineup tab` : "Lineup is valid", n ? "bad" : "ok"); if (n) app.showTab("lineup"); };
  app.save = async () => {
    if (!app.current) return;
    const name = app.current.name, dup = app.current.scope === "template";
    try {
      const saved = await api.saveLineup(name, app.current.raw, app.scope, dup);
      const positions = app.canvas.positions(); app.current = saved; app.current.layout = positions; app.dirty = false;
      await api.saveLayout(name, positions); app.canvas.setGraph(saved.graph.nodes, saved.graph.edges, positions);
      app.toast(`${name} saved to ${saved.scope} scope`, "ok"); await app.reloadLists(); status(); app.showTab(app.tab);
    } catch (e) { app.toast(e.message, "bad"); if (e.data && e.data.problems) { app.current.problems = e.data.problems; app.showTab("lineup"); status(); } }
  };
  app.apply = async () => {
    if (!app.current) return;
    const table = app.current.role_table || {}; const lines = Object.entries(table).map(([r, v]) => `<div class="add">+ roles.${esc(r)}: ${esc(typeof v === "object" ? v.model || JSON.stringify(v) : v)}</div>`).join("") + `<div class="add">+ team: ${esc(app.current.name)}</div><div class="add">+ roles.enabled: true</div>`;
    app.confirm(`Apply ${app.current.name}?`, "New sessions use this lineup. This writes the role table and the active team into ~/.halo/config.json, exactly like halo teams use.", lines, async () => {
      const r = await api.applyLineup(app.current.name); app.state = await api.state(); await app.reloadLists(); status();
      app.toast(`${app.current.name} is the active lineup`, "ok"); (r.notes || []).forEach((n) => app.toast(n, "warn"));
    });
  };
  app.newLineup = async (from) => {
    const name = window.prompt(from ? `New lineup from ${from}: name?` : "New lineup name?", from ? from + "-mine" : "my-lineup"); if (!name) return;
    try { const l = await api.newLineup(name.trim(), from || "balanced", app.scope); await app.reloadLists(); await app.selectLineup(l.name); app.toast(`${l.name} created`, "ok"); } catch (e) { app.toast((e.data && e.data.problems && e.data.problems[0]) || e.message, "bad"); }
  };
  app.newBio = async () => {
    const name = window.prompt("New agent bio name?", "my-agent"); if (!name) return;
    const from = window.prompt("Start from which shipped bio? (blank for a minimal one)", "general");
    try { const b = await api.newBio(name.trim(), from || undefined, app.scope); await app.reloadLists(); app.bioName = b.name; app.showTab("agent"); app.toast(`${b.name} created`, "ok"); } catch (e) { app.toast((e.data && e.data.problems && e.data.problems[0]) || e.message, "bad"); }
  };
  app.toggleTheme = () => { const r = document.documentElement; const next = r.dataset.theme === "light" ? "dark" : "light"; r.dataset.theme = next; try { localStorage.setItem("halo-studio-theme", next); } catch (e) {} };
  app.toggleRun = () => { app.runView = !app.runView; $("btn-run").classList.toggle("primary", app.runView); $("timeline").classList.toggle("on", app.runView); if (app.runView) pollRun(); else { clearTimeout(app._runTimer); app.canvas.setLive({}); $("status-session").textContent = ""; } };
  async function pollRun() {
    try {
      const s = await api.session(); const live = {}; const nodes = app.current ? app.current.graph.nodes : [];
      for (const a of s.agents || []) {
        const n = nodes.find((x) => (a.role && (x.alias === a.role || x.role === a.role)) || (a.model && x.model === a.model && !live[x.id]));
        if (n) live[n.id] = { state: a.status || "done", cost: a.cost_usd ? a.cost_usd.toFixed(3) : "", turns: a.turns || "", last: a.description || "" };
      }
      app.canvas.setLive(live);
      $("status-session").textContent = s.running ? `session ${String(s.session_id || "").slice(0, 8)} live · ${(s.agents || []).length} sub-agents · roles ${Object.entries(s.roles || {}).map(([k, v]) => `${k} $${v}`).join(", ") || "-"}` : "no live session";
      $("timeline").innerHTML = (s.agents || []).slice(-60).map((a) => `<i class="${a.is_error ? "error" : "subagent"}" title="${esc(a.description || a.agent_id || "")}"></i>`).join("");
    } catch (e) { $("status-session").textContent = "session: " + e.message; }
    app._runTimer = setTimeout(pollRun, 3000);
  }

  // -- wiring -----------------------------------------------------------------------
  app.canvas.onSelect = (ids) => { app.selected = ids; app.bioName = null; if (app.tab === "agent" || app.tab === "assignment") app.showTab(app.tab); };
  app.canvas.onOpen = (id) => { app.selected = [id]; app.showTab("assignment"); };
  let layoutTimer = null;
  app.canvas.onMove = () => { if (!app.current) return; clearTimeout(layoutTimer); layoutTimer = setTimeout(() => api.saveLayout(app.current.name, app.canvas.positions()).catch(() => {}), 500); };
  app.canvas.onDrop = async (name, x, y) => {
    if (!app.current) { app.toast("Pick a lineup first", "warn"); return; }
    const bio = app.bios.find((b) => b.name === name); const role = bio && ["main", "subagent", "reviewer", "researcher", "judge"].includes(bio.kind) ? bio.kind : "subagent";
    app.current.raw.agents = app.current.raw.agents || []; app.current.raw.agents.push({ agent: name, role: role === "main" && app.current.raw.agents.some((e) => e.role === "main") ? "subagent" : role });
    app.dirty = true; const r = await api.validate("lineup", app.current.raw, app.current.name); app.current.problems = r.problems; app.current.graph = r.graph;
    const pos = app.canvas.positions(); const added = r.graph.nodes[r.graph.nodes.length - 1]; pos[added.id] = { x, y };
    app.canvas.setGraph(r.graph.nodes, r.graph.edges, pos); const n = app.canvas.node(added.id); if (n) n.justDropped = true; app.canvas.select([added.id]); status();
  };
  $("lineup-list").addEventListener("click", (ev) => { const li = ev.target.closest("li[data-name]"); if (li) app.selectLineup(li.dataset.name); });
  $("lineup-select").addEventListener("change", (ev) => app.selectLineup(ev.target.value));
  $("starters").addEventListener("click", (ev) => { const b = ev.target.closest("button[data-name]"); if (b) app.selectLineup(b.dataset.name); });
  $("bio-list").addEventListener("click", (ev) => { const c = ev.target.closest(".bio-chip"); if (c) { app.bioName = c.dataset.name; app.showTab("agent"); } });
  $("bio-list").addEventListener("dragstart", (ev) => { const c = ev.target.closest(".bio-chip"); if (c) { ev.dataTransfer.setData("text/halo-bio", c.dataset.name); ev.dataTransfer.setData("text/plain", c.dataset.name); ev.dataTransfer.effectAllowed = "copy"; } });
  document.querySelectorAll(".scope-toggle button").forEach((b) => b.addEventListener("click", () => { app.scope = b.dataset.scope; document.querySelectorAll(".scope-toggle button").forEach((x) => x.classList.toggle("on", x === b)); }));
  $("btn-validate").onclick = app.validate; $("btn-save").onclick = app.save; $("btn-apply").onclick = app.apply; $("btn-run").onclick = app.toggleRun;
  $("btn-theme").onclick = app.toggleTheme; $("btn-palette").onclick = app.palette.open; $("btn-new-lineup").onclick = () => app.newLineup(); $("btn-new-bio").onclick = app.newBio;
  $("zoom-in").onclick = () => app.canvas.zoomBy(1.2); $("zoom-out").onclick = () => app.canvas.zoomBy(1 / 1.2); $("zoom-fit").onclick = () => app.canvas.fit(); $("zoom-100").onclick = () => app.canvas.zoomTo(1);
  document.addEventListener("keydown", (ev) => {
    const typing = /^(INPUT|TEXTAREA|SELECT)$/.test(document.activeElement.tagName);
    if ((ev.ctrlKey || ev.metaKey) && ev.key.toLowerCase() === "k") { ev.preventDefault(); app.palette.toggle(); return; }
    if ((ev.ctrlKey || ev.metaKey) && ev.key.toLowerCase() === "s") { ev.preventDefault(); app.save(); return; }
    if ((ev.ctrlKey || ev.metaKey) && ev.key === "Enter") { ev.preventDefault(); app.validate(); return; }
    if ((ev.ctrlKey || ev.metaKey) && ev.key.toLowerCase() === "n") { ev.preventDefault(); app.newLineup(); return; }
    if (typing) return;
    if (ev.key === "a") app.canvas.autoLayout(); else if (ev.key === "f") app.canvas.fit(); else if (ev.key === "?") studioTour(app, true);
    else if (ev.key === "[") document.body.classList.toggle("rail-hidden"); else if (ev.key === "]") document.body.classList.toggle("inspector-hidden");
    else if (ev.key === "Delete" || ev.key === "Backspace") app.removeSelected(); else if (ev.key === "Escape") app.canvas.select([]);
  });
  window.addEventListener("beforeunload", (ev) => { if (app.dirty) { ev.preventDefault(); ev.returnValue = ""; } });

  // -- boot --------------------------------------------------------------------------
  (async () => {
    try { const t = localStorage.getItem("halo-studio-theme"); if (t) document.documentElement.dataset.theme = t; } catch (e) {}
    try {
      app.state = await api.state();
      [app.models, app.tools] = await Promise.all([api.models().catch(() => []), api.tools().catch(() => [])]);
      await app.reloadLists();
      const first = app.state.active_team && app.lineups.some((l) => l.name === app.state.active_team) ? app.state.active_team : null;
      if (first) await app.selectLineup(first); else { $("canvas-empty").style.display = ""; status(); app.showTab("assignment"); }
      if (!/[?&]tour=off/.test(location.search)) studioTour(app);  // captures and tests pass ?tour=off
    } catch (e) {
      $("canvas-empty").style.display = ""; $("canvas-empty").querySelector("h2").textContent = "Studio cannot reach its server";
      $("canvas-empty").querySelector("p").textContent = e.message + " — open the exact URL `halo studio` printed (it carries the token).";
    }
  })();
})();
