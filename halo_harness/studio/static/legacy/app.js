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
  app.mode = "roles";
  app.setMode = async (mode) => {  // 2.2.0: Roles (lineups) | Org (the company in Paperclip)
    if (mode === app.mode) return;
    document.querySelectorAll(".mode-toggle button").forEach((b) => b.classList.toggle("on", b.dataset.mode === mode));
    try { localStorage.setItem("halo-studio-mode", mode); } catch (e) {}
    if (mode === "org") { window.designMode.leave(app); app.mode = "org"; app.canvas.select([]); await window.orgMode.enter(app); }
    else if (mode === "design") { window.orgMode.leave(app); app.mode = "design"; app.canvas.select([]); await window.designMode.enter(app); }  // 3.0.1.0
    else { window.orgMode.leave(app); window.designMode.leave(app); app.mode = "roles"; document.body.dataset.mode = "roles"; const heads = $("rail").querySelectorAll("h3"); heads[0].firstChild.textContent = "Lineups "; heads[1].firstChild.textContent = "Agents "; restoreTabs(); app.canvas.onMove = rolesOnMove; app.canvas.onDropOn = rolesDropOn; if (app.current) { const name = app.current.name; app.current = null; await app.selectLineup(name); } else { app.canvas.setGraph([], []); await app.reloadLists(); status(); } }
  };
  const TABS = ["assignment:Assignment", "agent:Agent", "lineup:Lineup", "yaml:YAML"];
  function restoreTabs() {
    $("inspector").querySelector(".tabs").innerHTML = TABS.map((t) => { const [k, l] = t.split(":"); return `<button data-tab="${k}" class="${k === app.tab ? "on" : ""}">${l}</button>`; }).join("");
    document.querySelectorAll("#inspector .tabs button").forEach((b) => b.addEventListener("click", () => app.showTab(b.dataset.tab)));
    app.showTab(app.tab);
  }
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
  // 3.0.2.0: connect a box to another box. The connection is the lineup's
  // own `org.positions[].reports_to` (titles = alias, else role, else agent);
  // "" (or main) means it hangs off the starting box again.
  app.titleOf = (entry) => entry.as || entry.role || entry.agent || "";
  app.setReportsTo = async (index, target) => {
    const raw = app.current.raw; const entry = raw.agents[index]; if (!entry) return;
    const title = app.titleOf(entry);
    raw.org = raw.org && typeof raw.org === "object" ? raw.org : {};
    raw.org.positions = Array.isArray(raw.org.positions) ? raw.org.positions : [];
    let pos = raw.org.positions.find((p) => p && p.title === title);
    const mainEntry = raw.agents.find((e) => e.role === "main");
    const toMain = !target || (mainEntry && target === app.titleOf(mainEntry));
    if (toMain) { if (pos) { delete pos.reports_to; if (Object.keys(pos).filter((k) => k !== "title" && k !== "agent").length === 0) raw.org.positions = raw.org.positions.filter((p) => p !== pos); } }
    else { if (!pos) { pos = { title, agent: entry.agent }; raw.org.positions.push(pos); } pos.reports_to = target; }
    if (!raw.org.positions.length) delete raw.org.positions;
    if (!Object.keys(raw.org).length) delete raw.org;
    await app.changed();
    app.toast(toMain ? `${title} hangs off the starting box again` : `${title} now reports to ${target}`, "ok");
  };
  const rolesDropOn = (draggedId, targetId) => {
    const g = app.current && app.current.graph; if (!g) return;
    const from = g.nodes.find((n) => n.id === draggedId), to = g.nodes.find((n) => n.id === targetId);
    if (!from || !to || from.role === "main") { if (from && from.role === "main") app.toast("the starting box stays the root; drag another card onto it instead", "warn"); return; }
    app.setReportsTo(from.index, app.titleOf(app.current.raw.agents[to.index]));
  };
  app.rolesDropOn = rolesDropOn;
  app.canvas.onLock = (id) => { app.showTab("agent"); app.toast("A shipped bio is read-only: press Duplicate in the Agent tab for an editable copy in your scope. The lock is a badge, not a switch.", "warn"); };
  app.changed = async () => { app.dirty = true; await app.refreshGraph(); if (app.tab !== "yaml") app.showTab(app.tab); else if (app.current._yamlBox) app.current._yamlBox.value = (await api.toYaml(app.current.raw)).yaml; };
  app.replaceRaw = async (raw) => { app.current.raw = raw; app.dirty = true; await app.refreshGraph(); };
  app.removeSelected = async () => { if (app.mode !== "roles") return; const n = app.selectedNode(); if (!n) return; app.current.raw.agents.splice(n.index, 1); app.selected = []; await app.changed(); };

  // -- tabs ----------------------------------------------------------------------
  app.showTab = async (tab) => {
    if (app.mode === "org") return window.orgMode.showTab(tab);
    if (app.mode === "design") return window.designMode.showTab(tab);
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
  app.canvas.onSelect = (ids) => { if (app.mode === "org") { window.orgMode.select(ids[0]); window.orgMode.rail(app); return; } app.selected = ids; app.bioName = null; if (app.tab === "agent" || app.tab === "assignment") app.showTab(app.tab); };
  app.canvas.onOpen = (id) => { if (app.mode === "org") { window.orgMode.select(id); window.orgMode.showTab("frame"); return; } app.selected = [id]; app.showTab("assignment"); };
  let layoutTimer = null;
  const rolesOnMove = () => { if (!app.current) return; clearTimeout(layoutTimer); layoutTimer = setTimeout(() => api.saveLayout(app.current.name, app.canvas.positions()).catch(() => {}), 500); };
  app.canvas.onMove = rolesOnMove;
  app.canvas.onDropOn = app.rolesDropOn;  // 3.0.2.0: drop a card onto another to connect them
  app.canvas.onDrop = async (name, x, y) => {
    if (!app.current) { app.toast("Pick a lineup first", "warn"); return; }
    const bio = app.bios.find((b) => b.name === name); const role = bio && ["main", "subagent", "reviewer", "researcher", "judge"].includes(bio.kind) ? bio.kind : "subagent";
    app.current.raw.agents = app.current.raw.agents || []; app.current.raw.agents.push({ agent: name, role: role === "main" && app.current.raw.agents.some((e) => e.role === "main") ? "subagent" : role });
    app.dirty = true; const r = await api.validate("lineup", app.current.raw, app.current.name); app.current.problems = r.problems; app.current.graph = r.graph;
    const pos = app.canvas.positions(); const added = r.graph.nodes[r.graph.nodes.length - 1]; pos[added.id] = { x, y };
    app.canvas.setGraph(r.graph.nodes, r.graph.edges, pos); const n = app.canvas.node(added.id); if (n) n.justDropped = true; app.canvas.select([added.id]); status();
  };
  $("lineup-list").addEventListener("click", (ev) => { const ag = ev.target.closest("li[data-agent]"); if (ag) { app.canvas.select([ag.dataset.agent]); return; } const li = ev.target.closest("li[data-name]"); if (li) app.selectLineup(li.dataset.name); });
  document.querySelectorAll(".mode-toggle button").forEach((b) => b.addEventListener("click", () => app.setMode(b.dataset.mode)));
  $("company-select").addEventListener("change", async () => { window.orgMode.company = null; await api.pcLink({ company_id: $("company-select").value }).catch(() => {}); await window.orgMode.refresh(app, true); });
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
    if (ev.key === "o") { app.setMode("org"); return; } if (ev.key === "r") { app.setMode("roles"); return; } if (ev.key === "d") { app.setMode("design"); return; }
    if (app.mode === "design" && window.designMode.key(ev)) return;
    if (ev.key === "a") app.canvas.autoLayout(); else if (ev.key === "f") app.canvas.fit(); else if (ev.key === "?") studioTour(app, true);
    else if (ev.key === "[") document.body.classList.toggle("rail-hidden"); else if (ev.key === "]") document.body.classList.toggle("inspector-hidden");
    else if (ev.key === "Delete" || ev.key === "Backspace") app.removeSelected(); else if (ev.key === "Escape") app.canvas.select([]);
  });
  window.addEventListener("beforeunload", (ev) => { if (app.dirty) { ev.preventDefault(); ev.returnValue = ""; } });

  // -- boot --------------------------------------------------------------------------
  app.reboot = () => boot();
  async function boot() {
    try { const t = localStorage.getItem("halo-studio-theme"); if (t) document.documentElement.dataset.theme = t; } catch (e) {}
    try {
      app.state = await api.state();
      [app.models, app.tools] = await Promise.all([api.models().catch(() => []), api.tools().catch(() => [])]);
      await app.reloadLists();
      const first = app.state.active_team && app.lineups.some((l) => l.name === app.state.active_team) ? app.state.active_team : null;
      if (first) await app.selectLineup(first); else { $("canvas-empty").style.display = ""; status(); app.showTab("assignment"); }
      if (!/[?&]tour=off/.test(location.search)) studioTour(app);  // captures and tests pass ?tour=off
      let saved = ""; try { saved = localStorage.getItem("halo-studio-mode") || ""; } catch (e) {}
      // 3.0.2.0: ?mode=roles|org|design (halo studio --mode, /roles, /org, /design) beats the saved mode
      const asked = (location.search.match(/[?&]mode=(roles|org|design)/) || [])[1];
      const mode = asked || saved;
      if (mode === "design") app.setMode("design"); else if (mode === "org") app.setMode("org");
    } catch (e) {
      $("canvas-empty").style.display = ""; $("canvas-empty").querySelector("h2").textContent = "Studio cannot reach its server";
      $("canvas-empty").querySelector("p").textContent = e.message + " — open the exact URL `halo studio` printed (it carries the token).";
      console.error("studio boot failed", e);
    }
  }
  boot();
})();
