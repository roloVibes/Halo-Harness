/* Halo Studio -- Org mode (2.2.0): the company in Paperclip on the same
   canvas. Agents are cards, reports-to lines are edges, dragging a card onto
   another re-parents it; the inspector edits the agent through Paperclip's
   API (via Studio's proxy) and embeds the agent's own Paperclip page. */
(function () {
  "use strict";
  const { h, esc, field, input, select, textarea, problems } = window.inspector;
  const $ = (id) => document.getElementById(id);
  const ROLES = ["ceo", "cto", "cmo", "cfo", "security", "engineer", "designer", "pm", "qa", "devops", "researcher", "general"];
  const org = window.orgMode = { status: null, company: null, agents: [], issues: [], goals: [], projects: [], selected: null, tab: "agent", _poll: null };
  const STATUS_CLASS = { running: "running", paused: "paused", terminated: "terminated", error: "error", idle: "idle" };

  org.baseUrl = () => (org.status && org.status.base_url) || "http://127.0.0.1:3100";
  org.prefix = () => (org.company && (org.company.issuePrefix || org.company.id)) || "";
  org.agentUrl = (a) => `${org.baseUrl()}/${org.prefix()}/agents/${a.id}`;

  // -- loading ------------------------------------------------------------------
  org.enter = async (app) => {
    document.body.dataset.mode = "org";
    $("inspector").querySelector(".tabs").innerHTML = ["agent:Agent", "issues:Issues", "frame:Paperclip", "company:Company"]
      .map((t) => { const [k, l] = t.split(":"); return `<button data-tab="${k}" class="${k === org.tab ? "on" : ""}">${l}</button>`; }).join("");
    $("inspector").querySelectorAll(".tabs button").forEach((b) => b.addEventListener("click", () => org.showTab(b.dataset.tab)));
    app.canvas.onDropOn = org.reparent;
    await org.refresh(app, true);
    if (!org._poll) org._poll = setInterval(() => { if (document.body.dataset.mode === "org" && org.company) org.refresh(app, false).catch(() => {}); }, 8000);
  };
  org.leave = (app) => { app.canvas.onDropOn = null; org.selected = null; };

  org.refresh = async (app, full) => {
    try { org.status = await api.pcStatus(); } catch (e) { org.status = { error: e.message, companies: [] }; }
    const st = org.status;
    $("org-badges").innerHTML = st.reachable ? `<span class="badge live">Paperclip ${esc(st.version)}</span>` : `<span class="badge">Paperclip ${st.installed ? "not running" : "not installed"}</span>`;
    if (!st.reachable) { org.company = null; org.agents = []; app.canvas.setGraph([], []); $("canvas-empty").style.display = ""; org.emptyState(app); org.rail(app); org.showTab("company"); return; }
    $("canvas-empty").style.display = "none";
    const sel = $("company-select");
    sel.innerHTML = st.companies.map((c) => `<option value="${esc(c.id)}"${(org.company ? org.company.id === c.id : c.id === st.company_id) ? " selected" : ""}>${esc(c.name)}</option>`).join("") || `<option value="">(no company)</option>`;
    const cid = sel.value || (st.companies[0] && st.companies[0].id);
    if (!cid) { org.company = null; app.canvas.setGraph([], []); $("canvas-empty").style.display = ""; org.emptyState(app, true); org.showTab("company"); return; }
    if (!org.company || org.company.id !== cid) full = true;
    org.company = await api.pc("GET", `companies/${cid}`);
    [org.agents, org.issues] = await Promise.all([api.pc("GET", `companies/${cid}/agents`), api.pc("GET", `companies/${cid}/issues`).catch(() => [])]);
    if (full) [org.goals, org.projects] = await Promise.all([api.pc("GET", `companies/${cid}/goals`).catch(() => []), api.pc("GET", `companies/${cid}/projects`).catch(() => [])]);
    org.draw(app, full);
    org.rail(app);
    if (full) org.showTab(org.tab);
    $("status-active").textContent = `company: ${org.company.name} · ${org.agents.length} agents · ${org.issues.filter((i) => ["todo", "in_progress", "blocked"].includes(i.status)).length} open issues`;
  };

  org.graph = () => {
    const nodes = org.agents.map((a) => ({
      id: a.id, kind: "org", agent: a.name, role: a.role, subtitle: `${a.role}${a.title ? " · " + a.title : ""}`,
      chip: `${a.adapterType || "?"}${a.metadata && a.metadata.halo_agent ? " · halo " + a.metadata.halo_agent : ""}`,
      metaHtml: `<span>${esc(a.status || "idle")}</span><span>$${((a.spentMonthlyCents || 0) / 100).toFixed(2)}${a.budgetMonthlyCents ? " / $" + (a.budgetMonthlyCents / 100).toFixed(0) : ""}</span>`,
      statusClass: STATUS_CLASS[a.status] || "idle", scope: "", problems: a.errorReason ? [a.errorReason] : [], warnings: a.orgChainHealth && a.orgChainHealth.status && a.orgChainHealth.status !== "ok" ? [JSON.stringify(a.orgChainHealth).slice(0, 120)] : [],
    }));
    const edges = org.agents.filter((a) => a.reportsTo).map((a) => ({ from: a.reportsTo, to: a.id, kind: "reports-to", label: "" }));
    return { nodes, edges };
  };
  org.draw = async (app, full) => {
    const g = org.graph();
    let layout = {};
    try { layout = await api.layout("pc:" + org.company.id); } catch (e) {}
    app.canvas.setGraph(g.nodes, g.edges, Object.keys(layout).length ? layout : null);
    if (full && !Object.keys(layout).length) app.canvas.fit();
    app.canvas.onMove = () => api.saveLayout("pc:" + org.company.id, app.canvas.positions()).catch(() => {});
  };
  org.agentById = (id) => org.agents.find((a) => a.id === id);
  org.select = (id) => { org.selected = org.agentById(id) || null; org.showTab(org.tab === "company" ? "agent" : org.tab); };

  org.reparent = (draggedId, targetId, node) => {
    const a = org.agentById(draggedId), boss = org.agentById(targetId);
    if (!a || !boss || a.reportsTo === boss.id) { window.app.canvas.render(); return; }
    window.app.confirm(`${a.name} reports to ${boss.name}?`, "This changes the reporting line in Paperclip (PATCH the agent's reportsTo).", "", async () => {
      await api.pc("PATCH", `agents/${a.id}`, { reportsTo: boss.id }); window.app.toast(`${a.name} now reports to ${boss.name}`, "ok"); await org.refresh(window.app, true);
    });
    window.app.canvas.render();
  };

  // -- rail --------------------------------------------------------------------------
  org.rail = (app) => {
    $("lineup-list").innerHTML = org.agents.map((a) => `<li data-agent="${esc(a.id)}" class="${org.selected && org.selected.id === a.id ? "active" : ""}"><span class="name">${esc(a.name)}</span><span class="badge ${esc(STATUS_CLASS[a.status] || "")}">${esc(a.status || "")}</span><span class="desc">${esc(a.title || a.role)}</span></li>`).join("") || `<li><span class="desc">no agents yet: Sync a lineup from the Company tab</span></li>`;
    const heads = $("rail").querySelectorAll("h3"); heads[0].firstChild.textContent = "Agents "; heads[1].firstChild.textContent = "Goals & projects ";
    $("bio-list").innerHTML = [...org.goals.map((g) => `<div class="bio-chip" style="cursor:default"><span class="dot" style="background:var(--warning)"></span>${esc(g.title || g.name)}<span class="model">goal</span></div>`),
      ...org.projects.map((p) => `<div class="bio-chip" style="cursor:default"><span class="dot" style="background:var(--accent)"></span>${esc(p.name)}<span class="model">project</span></div>`)].join("") || `<div class="hint" style="padding:0 16px">no goals or projects yet</div>`;
  };

  // -- inspector -----------------------------------------------------------------------
  org.showTab = async (tab) => {
    org.tab = tab; document.querySelectorAll("#inspector .tabs button").forEach((b) => b.classList.toggle("on", b.dataset.tab === tab));
    const body = $("inspector-body"); body.innerHTML = "";
    if (tab === "agent") org.agentTab(body); else if (tab === "issues") org.issuesTab(body); else if (tab === "frame") org.frameTab(body); else org.companyTab(body);
  };

  org.agentTab = (body) => {
    const a = org.selected;
    if (!a) { body.appendChild(h(`<p class="hint">Select an agent card, or pick one in the left rail.</p>`)); return; }
    const patch = {};
    body.appendChild(h(`<div class="section-head"><span>${esc(a.name)}</span><span class="badge ${esc(STATUS_CLASS[a.status] || "")}">${esc(a.status)}</span></div>`));
    body.appendChild(field("Title", input(a.title || "", (v) => (patch.title = v))));
    body.appendChild(field("Role", select(a.role || "general", ROLES, (v) => (patch.role = v))));
    body.appendChild(field("Reports to", select(a.reportsTo || "", ["", ...org.agents.filter((x) => x.id !== a.id).map((x) => x.id)], (v) => (patch.reportsTo = v || null)), "names are agent ids; the canvas drag does the same"));
    body.querySelectorAll("select").forEach((s) => [...s.options].forEach((o) => { const x = org.agentById(o.value); if (x) o.textContent = x.name; }));
    body.appendChild(field("Monthly budget (USD)", input(a.budgetMonthlyCents ? (a.budgetMonthlyCents / 100).toFixed(2) : "", (v) => (patch.budgetMonthlyCents = Math.round(parseFloat(v || "0") * 100)), 'type="number" step="1" min="0"'), `spent $${((a.spentMonthlyCents || 0) / 100).toFixed(2)} this month`));
    body.appendChild(h(`<div class="section-head"><span>adapter</span><span class="badge">${esc(a.adapterType || "")}</span></div>`));
    const cfg = a.adapterConfig || {};
    body.appendChild(h(`<div class="kv"><b>command</b><span class="mono">${esc(cfg.command || "")} ${esc((cfg.args || []).join(" "))}</span><b>cwd</b><span class="mono">${esc(cfg.cwd || "")}</span><b>halo bio</b><span>${esc((a.metadata || {}).halo_agent || "-")}</span><b>lineup</b><span>${esc((a.metadata || {}).halo_lineup || "-")}</span></div>`));
    const row = h(`<div style="display:flex;gap:8px;flex-wrap:wrap;margin-top:12px"></div>`);
    const save = h(`<button class="btn primary">Save</button>`);
    save.addEventListener("click", async () => { try { await api.pc("PATCH", `agents/${a.id}`, patch); window.app.toast(`${a.name} saved`, "ok"); await org.refresh(window.app, true); } catch (e) { window.app.toast(e.message, "bad"); } });
    row.appendChild(save);
    for (const [label, action, kind] of [["Wake", "wakeup", ""], [a.status === "paused" ? "Resume" : "Pause", a.status === "paused" ? "resume" : "pause", "ghost"], ["Terminate", "terminate", "danger ghost"]]) {
      const b = h(`<button class="btn ${kind}">${label}</button>`);
      b.addEventListener("click", () => window.app.confirm(`${label} ${a.name}?`, `POST /agents/${a.id}/${action} in Paperclip.`, "", async () => { await api.pc("POST", `agents/${a.id}/${action}`, {}); window.app.toast(`${a.name}: ${label.toLowerCase()}`, "ok"); await org.refresh(window.app, true); }));
      row.appendChild(b);
    }
    const open = h(`<a class="btn ghost" target="_blank" href="${esc(org.agentUrl(a))}">Open in Paperclip ↗</a>`);
    row.appendChild(open); body.appendChild(row);
    body.appendChild(problems(a.errorReason ? [a.errorReason] : []));
  };

  org.issuesTab = (body) => {
    const mine = org.selected ? org.issues.filter((i) => i.assigneeAgentId === org.selected.id) : org.issues;
    body.appendChild(h(`<div class="section-head"><span>${org.selected ? esc(org.selected.name) + "'s issues" : "All issues"}</span><span class="hint">${mine.length}</span></div>`));
    for (const i of mine.slice(0, 80)) {
      const r = h(`<div class="issue-row"><span class="id">${esc(i.identifier)}</span><span>${esc(i.title)}</span><span class="st ${esc(i.status)}">${esc(i.status)}</span></div>`);
      r.addEventListener("click", () => { org.frameUrl = `${org.baseUrl()}/${org.prefix()}/issues/${i.identifier}`; org.showTab("frame"); });
      body.appendChild(r);
    }
    body.appendChild(h(`<div class="section-head"><span>New issue</span></div>`));
    const title = input("", () => {}, 'placeholder="Title"'); const desc = textarea("", () => {}, 3); desc.placeholder = "What should be done";
    const who = select(org.selected ? org.selected.id : "", ["", ...org.agents.map((a) => a.id)], () => {});
    [...who.options].forEach((o) => { const x = org.agentById(o.value); if (x) o.textContent = x.name; if (!o.value) o.textContent = "(unassigned)"; });
    body.append(field("Title", title), field("Description", desc), field("Assign to", who, "an assigned agent is woken by Paperclip at once"));
    const btn = h(`<button class="btn primary">Create issue</button>`);
    btn.addEventListener("click", async () => {
      if (!title.value.trim()) return;
      try { await api.pc("POST", `companies/${org.company.id}/issues`, { title: title.value.trim(), description: desc.value, assigneeAgentId: who.value || undefined, status: "todo" }); window.app.toast("issue created", "ok"); await org.refresh(window.app, false); org.showTab("issues"); }
      catch (e) { window.app.toast(e.message, "bad"); }
    });
    body.appendChild(btn);
  };

  org.frameTab = (body) => {
    const url = org.frameUrl || (org.selected ? org.agentUrl(org.selected) : `${org.baseUrl()}/${org.prefix()}`);
    body.appendChild(h(`<div class="section-head"><span>Paperclip</span><a target="_blank" href="${esc(url)}">open ↗</a></div>`));
    body.appendChild(h(`<iframe class="pc-frame" src="${esc(url)}" title="Paperclip"></iframe>`));
    org.frameUrl = null;
  };

  org.companyTab = (body) => {
    const st = org.status || {};
    if (!st.reachable) { org.emptyState(body === $("inspector-body") ? window.app : window.app, false, body); return; }
    const c = org.company || {};
    body.appendChild(h(`<div class="section-head"><span>${esc(c.name || "company")}</span><span class="badge live">${esc(c.status || "")}</span></div>`));
    body.appendChild(h(`<div class="kv"><b>id</b><span class="mono">${esc(c.id || "")}</span><b>prefix</b><span>${esc(c.issuePrefix || "")}</span><b>budget</b><span>$${((c.spentMonthlyCents || 0) / 100).toFixed(2)} / $${((c.budgetMonthlyCents || 0) / 100).toFixed(0)} this month</span><b>Paperclip</b><span>${esc(st.base_url)} · ${esc(st.version)}</span></div>`));
    body.appendChild(h(`<div class="section-head"><span>Sync a lineup into this company</span></div>`));
    const pick = select("", (window.app.lineups || []).map((l) => l.name), () => {});
    body.appendChild(field("Lineup", pick, "one Paperclip agent per assignment, run through halo paperclip-run; reporting lines from the lineup's org section or everyone -> main"));
    const row = h(`<div style="display:flex;gap:8px;flex-wrap:wrap"></div>`);
    const sync = h(`<button class="btn primary">Sync lineup → company</button>`);
    sync.addEventListener("click", () => window.app.confirm(`Sync ${pick.value} into ${c.name}?`, "Creates or updates the agents; nothing is deleted.", "", async () => {
      const r = await api.pcSync({ lineup: pick.value, company_id: c.id }); window.app.toast(`${r.agents} agent(s) synced`, "ok"); await org.refresh(window.app, true);
    }));
    const pull = h(`<button class="btn">Pull reporting lines → lineup</button>`);
    pull.addEventListener("click", () => window.app.confirm(`Write ${c.name}'s reporting lines into ${pick.value}?`, "Saves org.positions into the lineup's YAML (your scope).", "", async () => {
      await api.pcPull({ lineup: pick.value, company_id: c.id }); window.app.toast("lineup updated", "ok");
    }));
    const open = h(`<a class="btn ghost" target="_blank" href="${esc(st.base_url)}/${esc(org.prefix())}">Open Paperclip ↗</a>`);
    row.append(sync, pull, open); body.appendChild(row);
  };

  org.emptyState = (app, noCompany = false, into = null) => {
    const st = org.status || {}; const box = into || $("canvas-empty").querySelector(".inner");
    if (!into) { box.querySelector("h2").textContent = noCompany ? "No company yet" : st.installed ? "Paperclip is installed but not running" : "Your company runs in Paperclip";
      box.querySelector("p").textContent = noCompany ? "Create one from a lineup: the Company tab's Sync, or the Paperclip UI." : st.installed ? "Start it with `npx paperclipai run`, then this view fills in." : "Paperclip is the open-source control plane for a company of agents: org chart, goals, issues, heartbeats, budgets. Halo's lineups become its agents.";
      $("starters").innerHTML = ""; return; }
    into.appendChild(h(`<div class="pc-empty"><h3 style="margin:0 0 6px">${st.installed ? "Paperclip is installed but not running" : "Install Paperclip"}</h3><p class="hint">${st.installed ? "Run <code>npx paperclipai run</code> in a terminal, or restart its service." : "Runs <code>npx paperclipai onboard --yes</code>: Node 24+, an embedded PostgreSQL under ~/.paperclip, the server on port 3100, loopback only."}</p></div>`));
    if (!st.installed) {
      const btn = h(`<button class="btn primary" ${st.node ? "" : "disabled"}>Install Paperclip</button>`); const log = h(`<div class="pc-log" style="margin-top:10px;display:none"></div>`);
      btn.addEventListener("click", async () => { try { await api.pcInstall(); btn.disabled = true; log.style.display = ""; const tick = async () => { const r = await api.pcInstallLog(); log.textContent = r.log.join("\n"); log.scrollTop = log.scrollHeight; if (r.running) setTimeout(tick, 1500); else { window.app.toast(r.code === 0 ? "Paperclip is up" : "install ended with code " + r.code, r.code === 0 ? "ok" : "bad"); org.refresh(window.app, true); } }; tick(); } catch (e) { window.app.toast(e.message, "bad"); } });
      into.append(btn, log);
      if (!st.node) into.appendChild(h(`<p class="hint">Node.js was not found on PATH; install Node 24 or newer first.</p>`));
    }
  };
})();
