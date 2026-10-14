/* Halo Studio -- the Agent tab: the bio behind the selected card (or any bio
   from the rail), every BIO section as typed fields, with the same
   validator the CLI uses behind Save. A shipped bio is duplicated into user
   scope under the same name on the first save, as the TUI's Duplicate does. */
(function () {
  "use strict";
  const { field, input, select, textarea, modelPicker, chips, problems, h, esc } = window.inspector;
  const KINDS = ["main", "subagent", "researcher", "judge", "reviewer", "custom", "media"];
  const EFFORTS = ["", "low", "medium", "high", "max"];

  function section(body, title, hint) {
    body.appendChild(h(`<div class="section-head"><span>${esc(title)}</span>${hint ? `<span class="hint">${esc(hint)}</span>` : ""}</div>`));
  }
  const num = (v) => (v === "" || v == null ? undefined : Number(v));
  function set(obj, key, v) { if (v === undefined || v === "" || v === null || (Array.isArray(v) && !v.length)) delete obj[key]; else obj[key] = v; }
  function sub(raw, key) { return (raw[key] = raw[key] && typeof raw[key] === "object" ? raw[key] : {}); }

  function turnsHint(models, limits) {
    const m = (window.app.models || []).find((x) => x.ref === models.preference);
    if (!m || !limits.max_budget_usd || !(m.price_in > 0)) return "";
    const perTurn = (m.price_in * 6 + (m.price_out || m.price_in) * 1.5) / 1000; // ~6k in, 1.5k out per turn
    return `about ${Math.max(1, Math.round(limits.max_budget_usd / perTurn))} turn(s) at this model's price`;
  }

  async function render(body, app) {
    const node = app.selectedNode();
    const name = app.bioName || (node && node.agent);
    if (!name) { body.appendChild(h(`<p class="hint">Select a card, or click an agent in the left rail, to edit its bio.</p>`)); return; }
    let bio;
    try { bio = await api.bio(name); } catch (e) { body.appendChild(problems([e.message])); return; }
    const raw = bio.raw; app.bio = bio;
    body.appendChild(h(`<div class="section-head"><span>${esc(name)}</span><span class="badge ${esc(bio.scope)}">${esc(bio.scope)}${bio.scope === "template" ? " · saves a copy to your scope" : ""}</span></div>`));
    body.appendChild(field("Description", input(raw.description || "", (v) => set(raw, "description", v))));
    body.appendChild(field("Kind", select(raw.kind || "subagent", KINDS, (v) => set(raw, "kind", v))));
    body.appendChild(field("Tags", chips(raw.tags = Array.isArray(raw.tags) ? raw.tags : [], (v) => set(raw, "tags", v))));
    body.appendChild(field("Extends", input(raw.extends || "", (v) => set(raw, "extends", v), 'placeholder="inherit every section from another bio"')));

    const models = sub(raw, "models");
    section(body, "models");
    body.appendChild(field("Preferred model", modelPicker(models.preference || "", (v) => { set(models, "preference", v); hint.textContent = turnsHint(models, limits); })));
    body.appendChild(field("Fallback", modelPicker(models.fallback || "", (v) => set(models, "fallback", v))));
    body.appendChild(field("Escalation target", modelPicker(models.escalation || "", (v) => set(models, "escalation", v), "a bigger model for when this one fails")));
    body.appendChild(field("Effort", select(models.effort || "", EFFORTS, (v) => set(models, "effort", v))));
    body.appendChild(field("Thinking", select(models.thinking || "", ["", "native", "off"], (v) => set(models, "thinking", v))));
    body.appendChild(field("Context budget (0-1)", input(models.context_budget ?? "", (v) => set(models, "context_budget", num(v)), 'type="number" step="0.05" min="0" max="1"')));

    const tools = sub(raw, "tools");
    section(body, "tools");
    body.appendChild(field("Allow", chips(tools.allow = Array.isArray(tools.allow) ? tools.allow : [], (v) => set(tools, "allow", v), { suggestions: app.tools || [] })));
    body.appendChild(field("Deny", chips(tools.deny = Array.isArray(tools.deny) ? tools.deny : [], (v) => set(tools, "deny", v), { suggestions: app.tools || [], cls: "deny" })));
    body.appendChild(field("Permission mode", select(tools.permission_mode || "", ["", "auto", "manual", "plan"], (v) => set(tools, "permission_mode", v))));
    body.appendChild(field("MCP servers", chips(tools.mcp_servers = Array.isArray(tools.mcp_servers) ? tools.mcp_servers : [], (v) => set(tools, "mcp_servers", v))));
    body.appendChild(field("Rules (one per line, settings.json grammar)", textarea((tools.rules || []).join("\n"), (v) => set(tools, "rules", v.split("\n").map((s) => s.trim()).filter(Boolean)), 3), 'e.g. deny Bash(git push*)'));

    const ctx = sub(raw, "context");
    section(body, "context");
    body.appendChild(field("Files prepended", chips(ctx.files = Array.isArray(ctx.files) ? ctx.files : [], (v) => set(ctx, "files", v))));
    body.appendChild(field("Skills", chips(ctx.skills = Array.isArray(ctx.skills) ? ctx.skills : [], (v) => set(ctx, "skills", v))));
    body.appendChild(field("System prompt", textarea(ctx.system_prompt || "", (v) => set(ctx, "system_prompt", v), 4)));

    const limits = sub(raw, "limits");
    section(body, "limits");
    body.appendChild(field("Max iterations", input(limits.max_iterations ?? "", (v) => set(limits, "max_iterations", num(v)), 'type="number" min="1"')));
    body.appendChild(field("Timeout", input(limits.timeout || "", (v) => set(limits, "timeout", v), 'placeholder="20m, 2h, 90s, 1d"')));
    const hint = h(`<div class="hint">${esc(turnsHint(models, limits))}</div>`);
    const budget = field("Max budget (USD)", input(limits.max_budget_usd ?? "", (v) => { set(limits, "max_budget_usd", num(v)); hint.textContent = turnsHint(models, limits); }, 'type="number" step="0.5" min="0"'));
    budget.appendChild(hint); body.appendChild(budget);
    body.appendChild(field("Concurrency", input(limits.concurrency ?? "", (v) => set(limits, "concurrency", num(v)), 'type="number" min="1"')));

    const out = sub(raw, "output");
    section(body, "output");
    body.appendChild(field("Handoff", select(out.handoff || "", ["", "summary", "full", "structured"], (v) => set(out, "handoff", v))));
    body.appendChild(field("Report to", input(out.report_to || "", (v) => set(out, "report_to", v), 'placeholder="boss"')));

    const env = sub(raw, "environment");
    section(body, "environment");
    const flags = h(`<div class="chips"></div>`);
    for (const key of ["worktree", "offline"]) {
      const lab = h(`<label class="chip"><input type="checkbox" ${env[key] ? "checked" : ""}> ${key}</label>`);
      lab.querySelector("input").addEventListener("change", (ev) => set(env, key, ev.target.checked || undefined));
      flags.appendChild(lab);
    }
    body.appendChild(flags);

    const acc = sub(raw, "acceptance");
    section(body, "acceptance", "halo doctor --agents runs this");
    body.appendChild(field("Prompt", input(acc.prompt || "", (v) => set(acc, "prompt", v))));
    body.appendChild(field("Expect (a substring, or non-empty)", input(acc.expect || "", (v) => set(acc, "expect", v))));

    const probs = h(`<div></div>`); body.appendChild(probs);
    const row = h(`<div style="display:flex;gap:8px;margin-top:16px;position:sticky;bottom:0;padding:8px 0;background:var(--surface)"></div>`);
    const save = h(`<button class="btn primary">Save bio</button>`);
    save.addEventListener("click", async () => {
      for (const k of Object.keys(raw)) if (raw[k] && typeof raw[k] === "object" && !Array.isArray(raw[k]) && !Object.keys(raw[k]).length) delete raw[k];
      try {
        const r = await api.saveBio(name, raw, app.scope, bio.scope === "template");
        probs.replaceChildren(problems([])); app.toast(`${name} saved (${r.scope})`, "ok"); await app.reloadLists(); app.refreshGraph();
      } catch (e) { probs.replaceChildren(problems(e.data?.problems?.length ? e.data.problems : [e.message])); }
    });
    const del = h(`<button class="btn danger ghost">Delete</button>`);
    del.addEventListener("click", () => app.confirm(`Delete ${name}?`, `Removes the ${bio.scope} file ${bio.path}. A shipped bio cannot be deleted.`, "", async () => { await api.deleteBio(name, app.scope); app.bioName = null; await app.reloadLists(); app.showTab("assignment"); }));
    row.append(save, del); body.appendChild(row);
  }

  window.bioForm = { render };
})();
