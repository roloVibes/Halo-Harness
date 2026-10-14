/* Halo Studio -- the inspector: the Assignment, Lineup and YAML tabs and the
   shared widgets (field, model picker, chips). The Agent tab lives in
   bio-form.js. Everything edits `app.current.raw` in place and calls
   app.changed() so the canvas, the status bar and the dirty flag follow. */
(function () {
  "use strict";
  const esc = (s) => String(s == null ? "" : s).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
  const h = (html) => { const t = document.createElement("template"); t.innerHTML = html.trim(); return t.content.firstElementChild; };
  const ROLES = ["main", "subagent", "reviewer", "researcher", "judge", "custom"];

  function field(label, control, hint) {
    const f = h(`<div class="field"><label>${esc(label)}</label></div>`);
    f.appendChild(control);
    if (hint) f.appendChild(h(`<div class="hint">${esc(hint)}</div>`));
    return f;
  }
  function input(value, onChange, attrs = "") {
    const i = h(`<input ${attrs} value="${esc(value)}">`);
    i.addEventListener("change", () => onChange(i.value));
    return i;
  }
  function select(value, options, onChange) {
    const s = h(`<select>${options.map((o) => `<option value="${esc(o)}"${o === value ? " selected" : ""}>${esc(o || "(none)")}</option>`).join("")}</select>`);
    s.addEventListener("change", () => onChange(s.value));
    return s;
  }
  function textarea(value, onChange, rows = 4) {
    const t = h(`<textarea rows="${rows}"></textarea>`); t.value = value || "";
    t.addEventListener("change", () => onChange(t.value));
    return t;
  }
  const ROUTE_NAMES = { or: "OpenRouter", ol: "Ollama", dbx: "Databricks", cc: "Claude Code subscription", cx: "Codex subscription",
                        ant: "Anthropic API", oai: "OpenAI API", hf: "Hugging Face", local: "Local server" };
  function modelGroup(m) {
    if (m.group) return m.group;
    const i = m.ref.indexOf(":"), route = i > 0 ? m.ref.slice(0, i) : "", rest = i > 0 ? m.ref.slice(i + 1) : m.ref;
    const name = ROUTE_NAMES[route] || route || "models";
    return route === "or" && rest.includes("/") ? `${name} · ${rest.split("/")[0]}` : name;
  }
  function modelLabel(m) {
    const bits = [m.ref.replace(/^or:[^/]+\//, ""), m.price, m.context ? `ctx ${m.context}` : ""];
    if (m.chips && m.chips !== "text") bits.push(m.chips);
    return bits.filter(Boolean).join(" · ");
  }
  function modelPicker(value, onChange, placeholder = "a model ref, or pick one") {
    // 3.0.2.0: a real dropdown -- every catalog row, grouped by route and vendor with price, context and
    // capability chips in the label -- behind a filter box, plus "Type a ref..." for a model the catalog lacks.
    const CUSTOM = "__custom__";
    const wrap = h(`<div class="model-pick"></div>`);
    const filter = h(`<input class="mono filter" placeholder="filter: deepseek, flash, 200k, vision...">`);
    const sel = h(`<select class="mono"></select>`);
    const custom = h(`<input class="mono" placeholder="${esc(placeholder)}" style="display:none">`);
    const hint = h(`<div class="hint"></div>`);
    const notice = h(`<div class="model-notice"></div>`);
    wrap.append(filter, sel, custom, hint, notice);
    const rows = () => window.app.models || [];
    const describe = (ref) => {
      const m = rows().find((x) => x.ref === ref);
      hint.textContent = m ? [m.price, m.context ? `ctx ${m.context}` : "", m.speed && m.speed !== "?" ? m.speed : "", m.chips && m.chips !== "text" ? m.chips : "", m.detail].filter(Boolean).join(" · ")
                           : (ref ? "not in the catalog (typed by hand)" : "");
    };
    const draw = () => {
      const q = filter.value.trim().toLowerCase();
      const groups = new Map();
      for (const m of rows()) {
        if (q && !(m.ref.toLowerCase().includes(q) || modelLabel(m).toLowerCase().includes(q) || modelGroup(m).toLowerCase().includes(q))) continue;
        const g = modelGroup(m); if (!groups.has(g)) groups.set(g, []); groups.get(g).push(m);
      }
      let html = `<option value="">(none)</option>`;
      const listed = [...groups.values()].some((ms) => ms.some((m) => m.ref === value));
      if (value && !listed) html += `<option value="${esc(value)}" selected>${esc(value)}${rows().some((m) => m.ref === value) ? "" : " (not in the catalog)"}</option>`;
      for (const [g, ms] of groups) html += `<optgroup label="${esc(g)} (${ms.length})">` + ms.map((m) => `<option value="${esc(m.ref)}"${m.ref === value ? " selected" : ""}>${esc(modelLabel(m))}</option>`).join("") + `</optgroup>`;
      html += `<option value="${CUSTOM}">Type a ref...</option>`;
      sel.innerHTML = html;
      describe(value);
    };
    filter.addEventListener("input", draw);
    sel.addEventListener("change", () => {
      if (sel.value === CUSTOM) { custom.style.display = ""; custom.value = value; custom.focus(); return; }
      value = sel.value; describe(value); onChange(value);
    });
    const commitCustom = () => { if (custom.style.display === "none") return; custom.style.display = "none"; value = custom.value.trim(); draw(); onChange(value); };
    custom.addEventListener("keydown", (ev) => { if (ev.key === "Enter") commitCustom(); if (ev.key === "Escape") { custom.style.display = "none"; draw(); } });
    custom.addEventListener("blur", commitCustom);
    draw();
    if (window.modelNotice) window.modelNotice(notice, draw);
    return wrap;
  }
  function chips(values, onChange, { suggestions = [], cls = "" } = {}) {
    const wrap = h(`<div class="chips"></div>`);
    const draw = () => {
      wrap.innerHTML = values.map((v, k) => `<span class="chip ${cls}">${esc(v)}<button data-k="${k}" class="btn ghost" style="height:18px;padding:0 4px" title="remove">×</button></span>`).join("");
      const add = h(`<input list="chip-sugg" placeholder="+ add" style="height:24px;width:110px;padding:0 8px;border-radius:999px;border:1px dashed var(--border);background:transparent">`);
      add.addEventListener("change", () => { if (add.value.trim()) { values.push(add.value.trim()); onChange(values); draw(); } });
      wrap.appendChild(add);
      wrap.querySelectorAll("button[data-k]").forEach((b) => b.addEventListener("click", () => { values.splice(Number(b.dataset.k), 1); onChange(values); draw(); }));
    };
    if (!document.getElementById("chip-sugg")) document.body.appendChild(h(`<datalist id="chip-sugg"></datalist>`));
    document.getElementById("chip-sugg").innerHTML = suggestions.map((s) => `<option value="${esc(s)}">`).join("");
    draw();
    return wrap;
  }
  function problems(list, cls = "") {
    if (!list || !list.length) return h(`<div></div>`);
    return h(`<ul class="problems">${list.map((p) => `<li class="${cls}">${esc(p)}</li>`).join("")}</ul>`);
  }

  // -- tabs -------------------------------------------------------------------
  function assignmentTab(body, app) {
    const node = app.selectedNode();
    if (!app.current) { body.appendChild(h(`<p class="hint">Pick a lineup on the left.</p>`)); return; }
    if (!node) { body.appendChild(h(`<p class="hint">Select a card on the canvas, or drag an agent from the left onto it, to edit an assignment.</p>`)); lineupHeader(body, app); return; }
    const entry = app.current.raw.agents[node.index];
    const bios = (app.bios || []).map((b) => b.name);
    body.appendChild(h(`<div class="section-head"><span>Assignment</span><span class="badge ${esc(node.scope)}">${esc(node.scope || "")}</span></div>`));
    body.appendChild(field("Agent (the bio behind this slot)", select(entry.agent || "", bios.includes(entry.agent) ? bios : [entry.agent || "", ...bios], (v) => { entry.agent = v; app.changed(); })));
    body.appendChild(field("Role", select(entry.role || "subagent", ROLES.includes(entry.role) ? ROLES : [entry.role, ...ROLES], (v) => { entry.role = v; app.changed(); }), "main runs the session; the others are the slots sub-agents fill"));
    body.appendChild(field("Alias (as)", input(entry.as || "", (v) => { if (v) entry.as = v; else delete entry.as; app.changed(); }, 'placeholder="worker, review, boss…"'), "routing and reports_to name this"));
    body.appendChild(field("Instances", input(String(entry.instances || 1), (v) => { entry.instances = Math.max(1, parseInt(v, 10) || 1); app.changed(); }, 'type="number" min="1"')));
    body.appendChild(field("Use for (words in a task that route here)", chips(entry.use_for = Array.isArray(entry.use_for) ? entry.use_for : [], () => app.changed())));
    if (entry.role !== "main") {  // 3.0.2.0: connect this box to another box
      const others = app.current.raw.agents.map((e, i) => ({ e, i })).filter(({ i }) => i !== node.index).map(({ e }) => app.titleOf(e)).filter(Boolean);
      const pos = ((app.current.raw.org || {}).positions || []).find((p) => p && p.title === app.titleOf(entry));
      const mainEntry = app.current.raw.agents.find((e) => e.role === "main");
      const current = pos && pos.reports_to && !(mainEntry && pos.reports_to === app.titleOf(mainEntry)) ? pos.reports_to : "";
      body.appendChild(field("Reports to (which box this one hangs off)", select(current, ["", ...others.filter((t) => t !== current), ...(current ? [current] : [])].filter((v, i, a) => a.indexOf(v) === i), (v) => app.setReportsTo(node.index, v)),
        "blank = the starting box. You can also drag this card onto another card on the canvas."));
    }
    const over = (entry.models = entry.models && typeof entry.models === "object" ? entry.models : {});
    body.appendChild(field("Model override (blank = the bio's own)", modelPicker(over.preference || "", (v) => { if (v) over.preference = v; else delete over.preference; if (!Object.keys(over).length) delete entry.models; app.changed(); })));
    body.appendChild(h(`<div class="section-head"><span>Resolved</span></div>`));
    body.appendChild(h(`<div class="hint">model <b class="mono">${esc(node.model || "none")}</b>${node.fallback ? ` · fallback <span class="mono">${esc(node.fallback)}</span>` : ""}${node.price ? ` · ${esc(node.price)}/M in` : ""}${node.context ? ` · ctx ${esc(node.context)}` : ""}</div>`));
    body.appendChild(problems(node.problems));
    body.appendChild(problems(node.warnings, "warn"));
    const row = h(`<div style="display:flex;gap:8px;margin-top:16px"></div>`);
    const openBio = h(`<button class="btn">Edit agent bio</button>`); openBio.addEventListener("click", () => app.showTab("agent"));
    const dup = h(`<button class="btn ghost">Duplicate</button>`); dup.addEventListener("click", () => { app.current.raw.agents.splice(node.index + 1, 0, JSON.parse(JSON.stringify(entry))); app.changed(); });
    const rm = h(`<button class="btn danger ghost">Remove</button>`); rm.addEventListener("click", () => app.removeSelected());
    row.append(openBio, dup, rm); body.appendChild(row);
  }

  function lineupHeader(body, app) {
    const raw = app.current.raw;
    body.appendChild(h(`<div class="section-head"><span>Lineup</span><span class="badge ${esc(app.current.scope)}">${esc(app.current.scope)}</span></div>`));
    body.appendChild(field("Description", input(raw.description || "", (v) => { raw.description = v; app.changed(); })));
    body.appendChild(field("How the pieces work together (about)", textarea(raw.about || "", (v) => { raw.about = v; app.changed(); }, 5), "shown to members as 'How this team works'"));
    body.appendChild(field("Extends", input(raw.extends || "", (v) => { if (v) raw.extends = v; else delete raw.extends; app.changed(); }, 'placeholder="another lineup to inherit sections from"')));
  }

  function lineupTab(body, app) {
    if (!app.current) { body.appendChild(h(`<p class="hint">Pick a lineup on the left.</p>`)); return; }
    lineupHeader(body, app);
    const raw = app.current.raw;
    for (const sec of app.state.top_sections || []) {
      const enf = (app.current.enforcement || {})[sec] || ["", ""];
      body.appendChild(h(`<div class="section-head"><span>${esc(sec)}</span><span class="badge" title="${esc(enf[1])}">${esc(enf[0] || "")}</span></div>`));
      const ta = textarea("", async (v) => {
        if (!v.trim()) { delete raw[sec]; app.changed(); return; }
        try { const r = await api.fromYaml(v); raw[sec] = r.raw; app.changed(); } catch (e) { app.toast(e.message, "bad"); }
      }, 4);
      ta.classList.add("yaml"); ta.style.height = "auto"; ta.placeholder = `${sec}: (YAML mapping body)`;
      body.appendChild(ta);
      if (raw[sec] != null) api.toYaml(raw[sec]).then((r) => { ta.value = r.yaml.trim(); ta.rows = Math.min(14, r.yaml.split("\n").length + 1); }).catch(() => {});
    }
    body.appendChild(problems(app.current.problems));
  }

  function yamlTab(body, app) {
    if (!app.current) { body.appendChild(h(`<p class="hint">Pick a lineup on the left.</p>`)); return; }
    const ta = h(`<textarea class="yaml" spellcheck="false"></textarea>`); ta.value = app.current.yaml || "";
    const row = h(`<div style="display:flex;gap:8px;margin:8px 0"></div>`);
    const applyBtn = h(`<button class="btn primary">Apply YAML to canvas</button>`);
    const out = h(`<div></div>`);
    applyBtn.addEventListener("click", async () => {
      try { const r = await api.fromYaml(ta.value); app.replaceRaw(r.raw); out.replaceChildren(problems([])); app.toast("YAML applied", "ok"); }
      catch (e) { out.replaceChildren(problems(e.data?.problems || [e.message])); }
    });
    const refresh = h(`<button class="btn ghost">Refresh from canvas</button>`); refresh.addEventListener("click", async () => { ta.value = (await api.toYaml(app.current.raw)).yaml; });
    row.append(applyBtn, refresh); body.append(row, ta, out);
    app.current._yamlBox = ta;
  }

  window.inspector = { field, input, select, textarea, modelPicker, chips, problems, h, esc, assignmentTab, lineupTab, yamlTab };
})();
