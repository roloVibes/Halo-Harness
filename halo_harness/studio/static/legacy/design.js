/* Halo Studio -- Design mode (3.0.1.0 round D3): the project state, the rail
   (projects, artboards, design system), live turns, the palette actions and
   the empty states. The canvas is design-canvas.js, the right panel is
   design-panel.js (Chat, Comments) and design-panel2.js (Knobs, System,
   Export). Everything the page keeps client-side is the card positions
   (localStorage, per project); the rest lives in ~/.halo/design/. */
(function () {
  "use strict";
  const { h, esc } = window.inspector;
  const $ = (id) => document.getElementById(id);
  const TABS = ["chat:Chat", "comments:Comments", "knobs:Knobs", "system:System", "export:Export"];
  const SUGGESTIONS = [
    "A landing page hero for a developer tool: a bold headline, one sentence, two buttons and a product screenshot area.",
    "A pricing section with three tiers, the middle one highlighted, using the design system's colours.",
    "A mobile onboarding flow of three screens as one prototype with tap-through steps, and add knobs for spacing and the accent colour.",
  ];
  const d = window.designMode = { app: null, slug: null, data: null, projects: [], ranking: [], media: [], tab: "chat", tool: "select", selected: null,
    view: {}, device: {}, editing: {}, bust: {}, turn: null, draft: "", exportLines: [], handoffPath: "", suggestions: SUGGESTIONS };

  d.toast = (m, k) => window.app.toast(m, k);
  d.call = (method, path, body, query) => api.design(method, d.slug + (path ? "/" + path : ""), body, query);
  d.active = () => document.body.dataset.mode === "design";
  d.live = () => !!(d.turn && !d.turn.done);
  d.artboard = (id) => ((d.data && d.data.artboards) || []).find((a) => a.id === id);
  d.openComments = () => ((d.data && d.data.comments) || []).filter((c) => !c.resolved);
  d.spent = () => ((d.data && d.data.history) || []).reduce((n, x) => n + (Number(x.cost) || 0), 0);

  // -- entering and leaving ---------------------------------------------------------
  d.enter = async (app) => {
    d.app = app; document.body.dataset.mode = "design";
    d.prevEmpty = $("canvas-empty").style.display; $("canvas-empty").style.display = "none";
    $("inspector").querySelector(".tabs").innerHTML = TABS.map((t) => { const [k, l] = t.split(":"); return `<button data-tab="${k}" class="${k === d.tab ? "on" : ""}">${l}</button>`; }).join("");
    $("inspector").querySelectorAll(".tabs button").forEach((b) => b.addEventListener("click", () => d.showTab(b.dataset.tab)));
    d.mountCanvas();
    await d.loadProjects();
    let last = ""; try { last = localStorage.getItem("halo-design-project") || ""; } catch (e) {}
    const pick = d.projects.find((p) => p.slug === last) || d.projects[0];
    if (pick) await d.open(pick.slug); else { d.slug = null; d.data = null; d.refreshAll(); }
    try { const t = (location.search.match(/[?&]dtab=(\w+)/) || [])[1]; if (t && d.data) d.showTab(t); } catch (e) {}  // captures open a tab with ?dtab=knobs
    d.loadRanking();
  };
  d.leave = (app) => { if (!d.app) return; d.app = null; $("canvas-empty").style.display = d.prevEmpty || "none"; };
  d.loadProjects = async () => { try { d.projects = (await api.design("GET", "projects")).projects; } catch (e) { d.projects = []; d.toast(e.message, "bad"); } };
  d.loadRanking = async () => { try { d.ranking = await api.design("GET", "models"); } catch (e) { d.ranking = []; }
    try { d.media = ((await api.design("GET", "models", undefined, { media: 1 })) || {}).media || []; } catch (e) { d.media = []; } if (d.active()) d.rail(); };
  d.llm = (v) => (String(v || "").startsWith("comfy:") ? "" : v);  // a media pick is a hint in the prompt, never the LLM model

  d.open = async (slug) => {
    d.slug = slug; d.view = {}; d.bust = {}; d.editing = {}; d.turn = null;
    const world = $("design-world"); if (world) world.innerHTML = "";
    try { localStorage.setItem("halo-design-project", slug); } catch (e) {}
    try { d.data = await d.call("GET", ""); } catch (e) { d.data = null; d.toast(e.message, "bad"); }
    const first = d.data && d.data.artboards[0];
    d.selected = first ? first.id : null;
    d.refreshAll();
    if (d.data && d.data.live_turn) d.attach(d.data.live_turn, "(a turn already running)");
  };
  d.reload = async (panel = true) => {
    if (!d.slug) return;
    d.data = await d.call("GET", "");
    if (!d.artboard(d.selected)) d.selected = d.data.artboards[0] ? d.data.artboards[0].id : null;
    d.rail(); d.drawCards(); d.empty(); d.status();
    if (panel) d.showTab(d.tab);
  };
  d.refreshAll = () => { d.rail(); d.drawCards(); d.empty(); d.status(); d.showTab(d.tab); };
  d.status = () => {
    const D = d.data; $("status-valid").textContent = D ? "design" : "no project"; $("status-valid").className = "";
    $("status-active").textContent = D ? `project: ${D.meta.name} · ${D.artboards.length} artboard(s) · ${d.openComments().length} open comment(s) · $${d.spent().toFixed(3)}` : "Design mode: create a project to start";
    document.title = (D ? D.meta.name + " · " : "") + "Halo Studio";
  };
  d.showTab = (tab) => {
    d.tab = tab; document.querySelectorAll("#inspector .tabs button").forEach((b) => b.classList.toggle("on", b.dataset.tab === tab));
    const body = $("inspector-body"); body.innerHTML = "";
    ({ chat: d.chatTab, comments: d.commentsTab, knobs: d.knobsTab, system: d.systemTab, export: d.exportTab }[tab] || d.chatTab)(body);
  };

  // -- turns (shared by Chat and Send comments) ----------------------------------------
  d.runTurn = async (prompt, opts = {}) => {
    if (!d.slug) { d.toast("Create or open a project first", "warn"); return null; }
    if (d.live()) { d.toast("A turn is already running in this project", "warn"); return null; }
    let hint = ""; if (String(opts.model || "").startsWith("comfy:")) { hint = opts.model.slice(6); opts = { ...opts, model: undefined }; }  // the turn's comfy_model hint
    try {
      const before = ((d.data && d.data.artboards) || []).map((a) => a.id);
      const r = await d.call("POST", "run", { prompt: hint ? prompt + " (comfy_model: " + hint + ")" : prompt, model: opts.model || undefined, budget: opts.budget || undefined, variants: opts.variants || undefined, base: opts.base || undefined });
      const done = await d.attach(r.turn, opts.variants ? `${opts.variants} directions: ${prompt}` : prompt);
      if (opts.variants && done && d.tileNew) d.tileNew(before);  // the new directions side by side, the first selected
      return done;
    } catch (e) { d.toast(e.message, "bad"); return null; }
  };
  d.attach = (tid, prompt) => new Promise((resolve) => {
    const turn = d.turn = { id: tid, prompt, events: [], next: 0, done: false, result: null };
    if (d.tab === "chat" && d.active()) d.showTab("chat");
    const tick = async () => {
      try {
        const p = await d.call("GET", `turn/${tid}`, undefined, { since: turn.next });
        turn.events.push(...p.events); turn.next = p.next;
        if (d.turn === turn && d.active()) d.paintEvents();
        if (!p.done) { setTimeout(tick, 500); return; }
        turn.done = true; turn.result = p.result;
        ((p.result && p.result.versions) || []).forEach((v) => { d.bust[v[0]] = (d.bust[v[0]] || 0) + 1; });  // the frames reload on the new version
        await d.reload(true);
        const r = p.result || {}; const vs = (r.versions || []).map((v) => `${v[0]} v${v[1]}`).join(", ");
        d.toast(r.code === 0 ? `Turn done: ${vs || "no artboard changed"}` : `Turn ended with exit ${r.code}${r.error ? ": " + r.error : ""}`, r.code === 0 ? "ok" : "bad");
        resolve(r);
      } catch (e) { turn.done = true; d.toast(e.message, "bad"); resolve(null); }
    };
    tick();
  });
  d.sendComments = async () => {
    const open = d.openComments();
    if (!open.length) { d.toast("No open comments to send", "warn"); return; }
    const lines = open.map((c) => `- [${c.artboard}] ${c.path ? c.path + " " : ""}at ${Math.round(c.x)}%,${Math.round(c.y)}% of the frame: ${c.text}`);
    const r = await d.runTurn("Address these comments:\n" + lines.join("\n"));
    if (r && r.code === 0) { await d.call("POST", "comments/resolve", { ids: open.map((c) => c.id) }); await d.reload(true); d.toast("Comments resolved", "ok"); }
  };

  // -- the rail -------------------------------------------------------------------------
  d.modelSelect = (value = "", withMedia = false) => {
    const rows = d.ranking.length ? d.ranking : (window.app.models || []).slice(0, 12).map((m) => ({ ref: m.ref, chips: m.chips, reason: m.price }));
    const opt = (r) => `<option value="${esc(r.ref)}"${r.ref === value ? " selected" : ""}>${esc(r.ref)}${r.chips && r.chips !== "text" ? " · " + esc(r.chips) : ""}${r.reason ? " · " + esc(String(r.reason).slice(0, 60)) : ""}</option>`;
    const gens = withMedia ? d.media.filter((m) => ["image-gen", "video-gen", "upscale", "tts"].includes(m.kind)) : [];
    const group = gens.length ? `<optgroup label="Media models (ComfyUI)">${gens.map((m) => `<option value="${esc(m.ref)}">${esc(m.file)} · ${esc(m.kind)}${m.quant && m.quant !== "unknown" ? " · " + esc(m.quant) : ""}</option>`).join("")}</optgroup>` : "";
    return h(`<select aria-label="Model"><option value="">(default model)</option>${rows.map(opt).join("")}${group}</select>`);
  };
  d.newForm = () => {
    const name = h(`<input placeholder="Project name" aria-label="Project name" maxlength="60">`); const model = d.modelSelect();
    const go = h(`<button class="btn primary">Create project</button>`); const form = h(`<div class="d-form"></div>`);
    const create = async () => {
      if (!name.value.trim()) { name.focus(); return; }
      try { const r = await api.design("POST", "projects", { name: name.value.trim(), model: model.value }); await d.loadProjects(); await d.open(r.slug); d.toast(`${name.value.trim()} created`, "ok"); }
      catch (e) { d.toast((e.data && e.data.problems && e.data.problems[0]) || e.message, "bad"); }
    };
    go.addEventListener("click", create); name.addEventListener("keydown", (ev) => { if (ev.key === "Enter") create(); });
    form.append(name, model, go); form.nameInput = name; return form;
  };
  d.openNew = () => { const f = $("d-newform"); if (f) { f.style.display = ""; f.querySelector("input").focus(); } else if ($("d-empty-name")) $("d-empty-name").focus(); };
  d.rail = () => {
    let root = $("design-rail"); if (!root) { root = h(`<div id="design-rail"></div>`); $("rail").appendChild(root); }
    const D = d.data;
    const projects = d.projects.map((p) => `<li data-slug="${esc(p.slug)}" class="${p.slug === d.slug ? "active" : ""}"><span class="name">${esc(p.name)}</span><span class="badge">${p.artboards}</span><span class="desc">${esc(p.model || "default model")}</span></li>`).join("");
    const boards = D ? D.artboards.map((a) => `<li data-id="${esc(a.id)}" class="${a.id === d.selected ? "active" : ""}"><span class="name">${esc(a.title || a.id)}</span><span class="badge">v${a.latest}</span><span class="desc">${esc(a.id)} · ${esc(a.kind)}${a.app ? ` · <span class="badge live">${esc(a.app)}</span>` : ""}</span></li>`).join("") : "";
    const groups = D ? Object.entries((D.system && D.system.tokens) || {}).map(([g, v]) => `<span class="d-chip">${esc(g)} <b>${Object.keys(v).length}</b></span>`).join("") : "";
    root.innerHTML = `<h3>Projects <button class="btn ghost" id="d-new" title="New project">+ new</button></h3><div id="d-newform" style="display:none"></div>
      <ul class="rail-list" id="d-projects">${projects || '<li><span class="desc">no projects yet</span></li>'}</ul>
      <h3>Artboards</h3><ul class="rail-list" id="d-boards">${boards || '<li><span class="desc">' + (D ? "none yet: run a turn" : "open a project") + "</span></li>"}</ul>
      <h3>Design system</h3><div class="d-sys">${groups || '<span class="hint">no tokens yet</span>'}</div>
      <div class="d-sync"><input id="d-sync-src" placeholder="Sync from… a folder path or URL" aria-label="Sync design system from"><button class="btn" id="d-sync-go"${D ? "" : " disabled"}>Sync</button></div>`;
    $("d-newform").appendChild(d.newForm());
    $("d-new").onclick = () => { const f = $("d-newform"); f.style.display = f.style.display === "none" ? "" : "none"; if (f.style.display === "") f.querySelector("input").focus(); };
    $("d-projects").onclick = (ev) => { const li = ev.target.closest("li[data-slug]"); if (li && li.dataset.slug !== d.slug) d.open(li.dataset.slug); };
    $("d-boards").onclick = (ev) => { const li = ev.target.closest("li[data-id]"); if (li) { d.selected = li.dataset.id; d.rail(); d.drawCards(); d.centerOn(li.dataset.id); if (d.tab === "knobs" || d.tab === "export") d.showTab(d.tab); } };
    $("d-sync-go").onclick = d.sync; $("d-sync-src").onkeydown = (ev) => { if (ev.key === "Enter") d.sync(); };
    if (d.paintAssets) d.paintAssets(root);
  };
  d.sync = async () => {
    const src = $("d-sync-src").value.trim(); if (!src || !d.slug) return;
    try { const r = await d.call("POST", "sync", { source: src }); d.toast(`Design system: ${r.tokens} token(s)`, "ok"); await d.reload(true); }
    catch (e) { d.toast(e.message, "bad"); }
  };

  // -- empty states and shortcuts -------------------------------------------------------
  d.empty = () => {
    const box = $("design-empty"); if (!box) return;
    const D = d.data;
    if (D && D.artboards.length) { box.style.display = "none"; return; }
    box.style.display = "";
    if (!D) {
      box.innerHTML = `<div class="inner"><h2>Design, on your own apps</h2><p>Prototypes, pages, decks and logos made with the models and craft apps you already have. Every turn is a version you can step back through.</p><div id="d-empty-form"></div></div>`;
      const f = d.newForm(); f.nameInput.id = "d-empty-name"; $("d-empty-form").appendChild(f); return;
    }
    box.innerHTML = `<div class="inner"><h2>${esc(D.meta.name)} is empty</h2><p>Pick a prompt to start from, or write your own in the Chat tab.</p><div class="starters">${d.suggestions.map((s, i) => `<button data-i="${i}"><b>${esc(s.split(":")[0].slice(0, 54))}</b><small>${esc(s)}</small></button>`).join("")}</div></div>`;
    box.querySelectorAll("button[data-i]").forEach((b) => b.addEventListener("click", () => { d.draft = d.suggestions[Number(b.dataset.i)]; d.showTab("chat"); const p = document.querySelector(".d-prompt"); if (p) p.focus(); }));
  };
})();
