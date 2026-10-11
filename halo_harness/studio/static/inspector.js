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
  function modelPicker(value, onChange, placeholder = "a model ref, or pick one") {
    const wrap = h(`<div class="model-pick"></div>`);
    const i = h(`<input class="mono" placeholder="${esc(placeholder)}" value="${esc(value)}">`);
    const menu = h(`<div class="menu" style="display:none"></div>`);
    wrap.append(i, menu);
    const draw = () => {
      const q = i.value.toLowerCase();
      const rows = (window.app.models || []).filter((m) => !q || m.ref.toLowerCase().includes(q)).slice(0, 60);
      menu.innerHTML = rows.map((m) => `<div data-ref="${esc(m.ref)}"><span>${esc(m.ref)}${m.chips && m.chips !== "text" ? ` <small class="chips-inline">${esc(m.chips)}</small>` : ""}</span><small>${esc(m.price)}</small><small>ctx ${esc(m.context)}</small><small>${esc(m.speed)}</small></div>`).join("") || `<div><small>no catalog rows match; type a ref and press Enter</small></div>`;
      menu.style.display = "";
    };
    i.addEventListener("focus", draw); i.addEventListener("input", draw);
    i.addEventListener("keydown", (ev) => { if (ev.key === "Enter") { menu.style.display = "none"; onChange(i.value.trim()); } if (ev.key === "Escape") menu.style.display = "none"; });
    i.addEventListener("blur", () => setTimeout(() => { menu.style.display = "none"; if (i.value.trim() !== value) onChange(i.value.trim()); }, 150));
    menu.addEventListener("mousedown", (ev) => { const d = ev.target.closest("[data-ref]"); if (d) { i.value = d.dataset.ref; onChange(d.dataset.ref); } });
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
