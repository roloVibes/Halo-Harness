// The coach pack's Coach panel in Studio's Agents section (Halo 3.4.0.0 B2: the run report's Coach tab was the
// core's until then; this panel is its one home now). Plain DOM, no build step:
// Studio loads it once the owner grants studio-script and calls mount(el, api). It lists Studio's repo's Orchestra
// runs (GET runs on the pack's routes), reads the picked run's card (GET orchestra/<run>/coach) and draws one block per
// suggestion -- its kind, its text, its why lines -- with Ask (the lead's paragraph), Apply (the confirm card first:
// the file and its diff; Confirm writes it) and Undo once applied. Probe shows the cost line first; Run probe starts it.

function h(tag, attrs, ...kids) {
  const el = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs || {})) {
    if (k === "onclick") el.addEventListener("click", v);
    else if (k === "style") el.setAttribute("style", v);
    else if (v !== null && v !== undefined) el.setAttribute(k, v);
  }
  for (const kid of kids) if (kid !== null && kid !== undefined) el.append(kid);
  return el;
}

const msg = (e) => (e && e.message ? e.message : String(e));

export function mount(el, api) {
  const client = api.lib && api.lib.api;
  const base = api.routes || "packs/coach/coach";
  const st = { runs: [], run: "", card: null, note: "", error: "", preview: null, probe: null, busy: false };
  const mono = "font-family: var(--font-mono, monospace); font-size: 12px; white-space: pre-wrap; margin: 0";
  const path = () => `${base}/orchestra/${encodeURIComponent(st.run)}/coach`;

  async function call(fn) {
    st.busy = true; st.error = ""; render();
    try { await fn(); } catch (e) { st.error = msg(e); }
    st.busy = false; render();
  }

  const loadCard = () => call(async () => {
    st.card = null; st.preview = null; st.probe = null;
    if (st.run) st.card = await client.get(path());
  });

  const ask = (id) => call(async () => { const got = await client.post(`${path()}/ask`, { id }); st.note = got.paragraph || got.error || ""; st.card = await client.get(path()); });
  const preview = (id) => call(async () => { st.preview = (await client.post(`${path()}/apply`, { id })).preview; });
  const confirm = () => call(async () => {
    const got = await client.post(`${path()}/apply`, { id: st.preview.id, confirm: true });
    st.note = `applied ${got.applied.apply_id}: ${got.applied.file}`; st.preview = null; st.card = await client.get(path());
  });
  const undo = (applyId) => call(async () => { st.note = (await client.post(`${path()}/undo`, { apply_id: applyId })).message; st.card = await client.get(path()); });
  const probe = (go) => call(async () => {
    const got = await client.post(`${path()}/probe`, { confirm: !!go });
    st.probe = got.estimate || null;
    st.note = go ? (got.started ? "probe started: its card leads this run's card when it ends" : "a probe of this run already runs") : "";
  });

  function suggestionBlock(s) {
    const applied = s.applied && s.applied.state === "applied" ? s.applied : null;
    return h("div", { "data-suggestion": s.id, style: "border-top: 1px solid var(--line, #8884); padding: 6px 0" },
      h("div", {}, h("strong", {}, `[${s.severity}] ${s.kind}`), s.bio ? ` (bio ${s.bio})` : "", s.lane_or_part ? ` · ${s.lane_or_part}` : ""),
      h("div", {}, s.text),
      h("pre", { style: mono }, (s.why || []).map((w) => `- ${w}`).join("\n")),
      s.paragraph ? h("p", { style: "margin: 4px 0" }, s.paragraph) : null,
      h("div", { style: "display:flex; gap:6px; margin-top:4px" },
        h("button", { type: "button", "data-act": "ask", onclick: () => ask(s.id) }, "Ask"),
        s.apply && !applied ? h("button", { type: "button", "data-act": "apply", onclick: () => preview(s.id) }, "Apply") : null,
        applied ? h("button", { type: "button", "data-act": "undo", onclick: () => undo(applied.apply_id) }, `Undo ${applied.apply_id}`) : null));
  }

  function render() {
    el.replaceChildren();
    const pick = h("select", { "data-part": "runs", "aria-label": "Run" }, h("option", { value: "" }, st.runs.length ? "Pick a run" : "No Orchestra run in this repo yet"));
    for (const r of st.runs) {
      const o = h("option", { value: r.run_id }, `${r.run_id} ${r.state}: ${(r.goal_what || "").slice(0, 60)}`);
      if (r.run_id === st.run) o.selected = true;
      pick.append(o);
    }
    pick.addEventListener("change", () => { st.run = pick.value; loadCard(); });
    el.append(h("div", { style: "display:flex; gap:8px; align-items:center; margin-bottom:8px" }, h("strong", {}, "Coach"), pick,
      st.run ? h("button", { type: "button", "data-act": "probe", onclick: () => probe(false) }, "Probe...") : null,
      st.busy ? h("span", {}, "...") : null));
    if (st.error) el.append(h("p", { "data-part": "error", style: "color: var(--danger, #c33); margin: 0 0 8px" }, st.error));
    if (st.note) el.append(h("p", { "data-part": "note", style: "margin: 0 0 8px" }, st.note));
    if (st.probe) {
      el.append(h("div", { "data-part": "probe" }, h("pre", { style: mono }, st.probe.line || ""),
        h("button", { type: "button", "data-act": "probe-run", onclick: () => probe(true) }, "Run probe")));
    }
    if (st.preview) {
      const p = st.preview;
      el.append(h("div", { "data-part": "preview" },
        h("pre", { style: mono }, [`apply ${p.id}: ${p.target} ${p.name || ""}: ${p.field} = ${JSON.stringify(p.value)}`,
          `file: ${p.file || (p.files || []).join(", ")}`, ...(p.diff || ["(no change: the file already holds it)"])].join("\n")),
        h("div", { style: "display:flex; gap:6px" },
          h("button", { type: "button", "data-act": "confirm", onclick: confirm }, "Confirm: write it"),
          h("button", { type: "button", "data-act": "cancel", onclick: () => { st.preview = null; render(); } }, "Cancel"))));
    }
    const c = st.card;
    if (!c) return;
    const rows = c.suggestions || [];
    el.append(h("p", { "data-part": "head", style: "margin: 0 0 4px" },
      `${c.kind} run ${c.run}: ${rows.length ? `${rows.length} suggestion(s)` : "nothing to suggest (the run's files show no finding)"}`));
    if (c.library_line) el.append(h("p", { "data-part": "library", style: "margin: 0 0 4px" }, c.library_line));
    for (const s of rows) el.append(suggestionBlock(s));
  }

  render();
  call(async () => { st.runs = (await client.get(`${base}/runs`)).runs || []; });
  return () => el.replaceChildren();
}
