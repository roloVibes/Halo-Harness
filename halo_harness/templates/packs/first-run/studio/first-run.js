// The first-run pack's panel in Studio's Agents section (Halo 3.4.0.0 B: "Start here" and "Test this lineup" were the
// core's until then; the pack's panel is their one home now). Plain DOM, no build step: Studio loads this module once
// the owner grants studio-script and calls mount(el, api). It reads GET start from the pack's own routes
// (server/routes.py), draws the card -- what the run does, the lineup, the models, the cost, the time, what it writes --
// and Run; once running, its seven steps arrive as `start` frames (the routes' ctx.publish, heard through api.on) and
// show as one row each, then the summary. Stop asks the run to end. On the Auto lineup (or none) Run is off and the
// line that says why stands in its place.

const STATE_MARK = { pending: "  ", ready: "..", running: ">>", done: "ok", failed: "!!", stopped: "--" };

function h(tag, attrs, ...kids) {
  const el = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs || {})) {
    if (k === "onclick") el.addEventListener("click", v);
    else if (k === "style") el.setAttribute("style", v);
    else el.setAttribute(k, v);
  }
  for (const kid of kids) if (kid !== null && kid !== undefined) el.append(kid);
  return el;
}

export function mount(el, api) {
  const client = api.lib && api.lib.api;
  const base = api.routes || "packs/first-run/start";
  const st = { status: null, steps: {}, summary: null, running: false, error: "", busy: false };
  const mono = "font-family: var(--font-mono, monospace); font-size: 12px; white-space: pre-wrap; margin: 0";

  function render() {
    el.replaceChildren();
    const s = st.status || {};
    const auto = s.auto || "";
    const head = h("div", { style: "display:flex; gap:8px; align-items:center; margin-bottom:8px" },
      h("strong", {}, "The guided first run"),
      h("button", { type: "button", "data-act": "run", disabled: st.running || st.busy || auto ? "" : null,
                    onclick: run }, st.running ? "Running..." : "Run"),
      st.running ? h("button", { type: "button", "data-act": "stop", onclick: stop }, "Stop") : null);
    if (!(st.running || st.busy || auto)) head.querySelector("[data-act=run]").removeAttribute("disabled");
    el.append(head);
    if (auto) el.append(h("p", { "data-part": "auto", style: "margin:0 0 8px" }, auto));
    if (st.error) el.append(h("p", { "data-part": "error", style: "color: var(--danger, #c33); margin:0 0 8px" }, st.error));
    const steps = Object.values(st.steps).sort((a, b) => a.step - b.step);
    if (steps.length) {
      const list = h("div", { "data-part": "steps" });
      for (const f of steps) {
        list.append(h("div", { "data-step": f.key, style: "margin-bottom:6px" },
          h("div", {}, `[${STATE_MARK[f.state] || f.state}] Step ${f.step} of ${f.total || 7}: ${f.title}`),
          (f.lines || []).length ? h("pre", { style: mono }, (f.lines || []).slice(-8).join("\n")) : null));
      }
      el.append(list);
    } else {
      el.append(h("pre", { "data-part": "card", style: mono }, (s.card || ["reading the card..."]).join("\n")));
    }
    if (st.summary) {
      const sm = st.summary;
      el.append(h("p", { "data-part": "summary", style: "margin-top:8px" }, sm.ok
        ? `Done: lineup ${sm.lineup}, run ${sm.run} in ${sm.repo}.`
        : `Stopped at ${sm.stopped_at || "the start"}: ${sm.reason || "no reason given"}`
          + (sm.error_log ? ` (the full error: ${sm.error_log})` : "")));
    }
  }

  function take(job) {
    if (!job) return;
    st.running = !!job.running;
    for (const f of job.steps || []) st.steps[f.key] = f;
    st.summary = job.summary || st.summary;
  }

  async function load() {
    try {
      st.status = await client.get(`${base}/start`);
      take(st.status.job);
    } catch (e) {
      st.error = `the card could not be read: ${e && e.message ? e.message : e}`;
    }
    render();
  }

  async function run() {
    st.busy = true; st.error = ""; st.steps = {}; st.summary = null;
    render();
    try {
      const got = await client.post(`${base}/start`, {});
      take(got.job);
    } catch (e) {
      st.error = e && e.message ? e.message : String(e);
    }
    st.busy = false;
    render();
  }

  async function stop() {
    try { await client.post(`${base}/stop`, {}); } catch (e) { st.error = String(e && e.message ? e.message : e); }
    render();
  }

  const off = api.on("start", (frame) => {
    const d = frame.data || {};
    if (d.key === "summary") { st.summary = d.summary || null; st.running = false; }
    else if (d.key) { st.steps[d.key] = d; st.running = true; }
    render();
  });
  render();
  load();
  return () => { off(); el.replaceChildren(); };
}
