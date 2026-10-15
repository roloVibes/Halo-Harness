/* Halo Studio -- the Inspector's Live tab on the Roles and Org canvases
   (3.0.5.0 R3; live.js adds the tab and feeds it). For the selected card:
   a chip per agent when several run on it, then the one you pick: state,
   harness, session, model, cost, elapsed, what it was asked, its three
   streams (Thinking: its text as it types it, character by character;
   Working: one row per tool call with its result; Output: its hand-back),
   Pause / Resume, Stop (asks first), Follow, Pin, and the Steer box (a
   nudge or a redirect, echoed in the stream as "you"). With nobody on the
   card, its track record: the last runs under that role (GET
   fleet/history through the shell). */
(function () {
  "use strict";
  const live = window.haloLive; if (!live) return;
  const app = window.app, { h, esc } = window.inspector;
  const $ = (id) => document.getElementById(id);
  const typer = { key: "", n: 0, timer: 0 };
  const T = window.haloLiveTab = {};
  const cost = (v) => "$" + (Number(v) || 0).toFixed(4);
  const ago = (ts) => { const s = Math.max(0, Date.now() / 1000 - (Number(ts) || 0)); return s < 60 ? `${Math.round(s)}s` : s < 3600 ? `${Math.round(s / 60)}m` : `${Math.round(s / 3600)}h`; };
  const pane = () => $("inspector-body").querySelector('[data-testid="live-pane"]');
  const current = () => (live.byNode[live.card] || []).find((a) => a.key === live.watched) || null;
  const nodeLabel = (n) => (n ? (n.alias && n.alias !== n.role ? `${n.agent} (${n.alias})` : n.agent) : "");

  // -- the streams --------------------------------------------------------------------------------
  function rows(entries) {
    const results = {}; for (const e of entries) if (e.kind === "tool_result" && e.id) results[e.id] = e;
    if (live.sub === "working") {
      const calls = entries.filter((e) => e.kind === "tool_call" || e.kind === "spawn");
      if (!calls.length) return `<p class="hint">No tool call yet: each one shows here with its result.</p>`;
      return calls.map((e) => { const r = results[e.id]; const st = r ? (r.is_error ? "error" : "done") : "running";
        const label = e.kind === "spawn" ? `${e.name}: ${e.task || ""}` : e.label || e.name;
        return `<div class="live-tool-row" data-state="${st}" data-testid="live-tool-row"><span class="live-glyph">${esc(live.glyph(String(e.name || "")))}</span><span class="mono live-tool-label">${esc(label)}</span><span class="live-tool-state">${st}</span>${r && r.text ? `<pre class="live-result">${esc(String(r.text).split("\n").slice(0, 6).join("\n"))}</pre>` : ""}</div>`; }).join("");
    }
    if (live.sub === "output") {
      const hand = [...entries].reverse().find((e) => e.kind === "handback"); let text = hand ? hand.text : "";
      if (!text) { const out = []; for (let i = entries.length - 1; i >= 0; i--) { const e = entries[i]; if (e.kind === "text") out.unshift(e.text || ""); else if (["tool_call", "spawn", "user"].includes(e.kind)) break; } text = out.join(""); }
      return text ? `<div class="live-output" data-testid="live-output"><span class="live-typed"></span></div>` : `<p class="hint">No hand-back yet.</p>`;
    }
    const list = entries.filter((e) => ["text", "thinking", "user", "note", "control", "ask", "error", "done"].includes(e.kind) && !(e.kind === "control" && /^agent_(follow|tail)$/.test(e.cmd || "")));
    if (!list.length) return `<p class="hint">Nothing written yet: its text shows here as it types it.</p>`;
    return list.map((e, i) => {
      if (e.kind === "user") return `<div class="live-row live-user" data-you="${e.you ? "1" : ""}"><b class="mono">${e.you ? "you · " + esc(e.mode || "nudge") : "asked"}</b> ${esc(e.text)}</div>`;
      if (e.kind !== "text" && e.kind !== "thinking") return `<div class="live-row live-note" data-kind="${esc(e.kind)}"><b class="mono">${esc(e.kind)}</b> ${esc(e.text || e.cmd || e.what || e.reason || "")}</div>`;
      return `<div class="live-row" data-kind="${e.kind}" data-testid="live-text">${i === list.length - 1 ? `<span class="live-typed"></span>` : esc(e.text)}</div>`;
    }).join("");
  }
  /** The newest text types out: it catches up in about 20 steps, never all at once. */
  function type(el, text) {
    if (!el) return;
    const key = live.watched + "|" + live.sub;
    if (typer.key !== key || typer.n > text.length) { typer.key = key; typer.n = Math.max(0, text.length - 40); }
    clearInterval(typer.timer);
    const step = () => { typer.n = Math.min(text.length, typer.n + Math.max(1, Math.ceil((text.length - typer.n) / 20))); el.textContent = text.slice(0, typer.n); if (typer.n >= text.length) clearInterval(typer.timer); };
    step(); typer.timer = setInterval(step, 30);
  }
  function paintStream() {
    const box = $("inspector-body").querySelector('[data-testid="live-stream"]'); if (!box) return;
    const d = live.stream, entries = (d && d.entries) || [];
    box.innerHTML = d ? rows(entries) : `<p class="hint">reading its stream...</p>`;
    const el = box.querySelector(".live-typed");
    if (el) {
      let text = "";
      if (live.sub === "output") { const hand = [...entries].reverse().find((e) => e.kind === "handback"); text = hand ? hand.text : ""; if (!text) { const out = []; for (let i = entries.length - 1; i >= 0; i--) { const e = entries[i]; if (e.kind === "text") out.unshift(e.text || ""); else if (["tool_call", "spawn", "user"].includes(e.kind)) break; } text = out.join(""); } }
      else { const t = entries.filter((e) => e.kind === "text" || e.kind === "thinking"); text = t.length ? t[t.length - 1].text || "" : ""; }
      type(el, text);
    }
    if (live.follow) box.scrollTop = box.scrollHeight;
  }
  T.stream = () => paintStream();

  // -- the commands (the shell runs them) -------------------------------------------------------------
  T.command = async (cmd, extra) => {
    const a = current(); if (!a) return;
    if (cmd === "pause" && a.state === "paused") cmd = "resume";
    const r = await live.ask({ type: "fleet-command", key: a.key, cmd, ...(extra || {}) });
    if (!r.ok) app.toast(r.error || `${cmd} did not go through`, "bad");
    else if (cmd !== "steer") app.toast(r.asked ? "Waiting for that harness's owner" : `${a.name}: ${cmd === "stop" ? "stopping at its next step" : cmd + "d"}`, "ok");
    return r;
  };
  T.toggleFollow = () => { live.follow = !live.follow; const b = pane() && pane().querySelector('[data-act="follow"]'); if (b) { b.classList.toggle("primary", live.follow); b.classList.toggle("ghost", !live.follow); } app.toast(live.follow ? "Follow on: the stream scrolls with it" : "Follow off", "ok"); };

  // -- the pane ---------------------------------------------------------------------------------------
  async function history(body, node) {
    const box = h(`<div class="live-history" data-testid="live-history"><div class="section-head"><span>Last runs under this role</span></div><p class="hint">reading the history...</p></div>`);
    body.appendChild(box);
    const pc = node.kind === "org" && window.orgMode ? window.orgMode.agentById(node.id) : null;
    const r = await live.ask({ type: "fleet-history", role: node.role || "", bio: pc ? (pc.metadata || {}).halo_agent || "" : node.agent || "" });
    const runs = (r && r.runs) || [];
    box.querySelector(".hint").outerHTML = runs.length ? `<ul class="live-runs">${runs.map((x) => `<li><span class="mono">${esc(ago(x.finished || x.started))} ago</span> <b>${esc(x.bio || x.role || "")}</b> <span class="badge ${x.is_error ? "bad" : ""}">${esc(x.is_error ? "failed" : x.status || "")}</span> <span class="mono">${esc(cost(x.cost_usd))}</span><div class="hint">${esc(x.task || "")}</div></li>`).join("")}</ul>` : `<p class="hint">${r && r.ok === false ? esc(r.error || "") : "No run under this role on this harness yet."}</p>`;
  }
  T.render = (body) => {
    const keep = body.querySelector('[data-testid="live-steer"]'), text = keep ? keep.value : "", focused = keep && document.activeElement === keep;
    body.innerHTML = "";
    const node = app.canvas.node(live.card), list = live.byNode[live.card] || [];
    const root = h(`<div class="live-pane" data-testid="live-pane"></div>`); body.appendChild(root);
    if (!node) { root.appendChild(h(`<p class="hint">Select a card: the agents that run under it right now, or its last runs, show here. J / K hop between the working cards.</p>`)); return; }
    if (!list.length) { root.appendChild(h(`<div class="section-head"><span>${esc(nodeLabel(node))}</span><span class="badge">nobody runs it now</span></div>`)); history(root, node); return; }
    const a = current() || list[0];
    if (list.length > 1) root.appendChild(h(`<div class="live-chips">${list.map((x) => `<button class="chip live-chip${x.key === a.key ? " on" : ""}" data-key="${esc(x.key)}" data-live="${esc(x.activity)}">${esc(x.name)} <small>${esc(x.harness)} · ${esc(x.state)}</small></button>`).join("")}</div>`));
    root.appendChild(h(`<div class="section-head live-head"><span>${esc(a.name)}${a.role && a.role !== a.name ? ` <small class="mono">${esc(a.role)}</small>` : ""}</span><span class="badge live-badge-state" data-live="${esc(a.activity)}">${esc(a.state)}</span></div>`));
    root.appendChild(h(`<div class="hint mono live-meta">${esc(a.harness)} · ${esc(a.session)} · ${esc(a.model || "model ?")} · ${esc(cost(a.cost_usd))}${a.since && live.isLive(a) ? " · " + esc(ago(a.since)) : ""}${a.current ? " · " + esc(a.current) : ""}</div>`));
    if (a.task) root.appendChild(h(`<details class="live-task"><summary>What it was asked</summary><p>${esc(a.task)}</p></details>`));
    root.appendChild(h(`<div class="live-subtabs">${["thinking:Thinking", "working:Working", "output:Output"].map((s) => { const [k, l] = s.split(":"); return `<button class="${live.sub === k ? "on" : ""}" data-sub="${k}">${l}</button>`; }).join("")}</div>`));
    root.appendChild(h(`<div class="live-stream" data-testid="live-stream"></div>`));
    const off = a.control === "none" || !live.isLive(a);
    root.appendChild(h(`<div class="live-actions"><button class="btn" data-act="pause"${off ? " disabled" : ""}>${a.state === "paused" ? "Resume" : "Pause"}</button><button class="btn danger ghost" data-act="stop"${off ? " disabled" : ""} data-testid="live-stop">Stop</button><button class="btn ${live.follow ? "primary" : "ghost"}" data-act="follow">Follow</button><button class="btn ${live.pinned === a.key ? "primary" : "ghost"}" data-act="pin">${live.pinned === a.key ? "Pinned" : "Pin"}</button></div>`));
    const steer = h(`<div class="live-steer"><div class="field"><label>Steer ${esc(a.name)} (only this agent hears it)</label><textarea rows="2" data-testid="live-steer" placeholder="${off ? "it takes no steer now" : "Say what to change; Enter sends"}"${off ? " disabled" : ""}></textarea></div><div class="live-steer-row"><select data-testid="live-steer-mode"><option value="nudge">nudge: a note before its next step</option><option value="redirect">redirect: a new task</option></select><button class="btn primary" data-act="steer" data-testid="live-steer-send"${off ? " disabled" : ""}>Send</button></div></div>`);
    root.appendChild(steer);
    const ta = steer.querySelector("textarea"); ta.value = text; if (focused) ta.focus();
    const send = async () => { const v = ta.value.trim(); if (!v) return; const r = await T.command("steer", { text: v, mode: steer.querySelector("select").value }); if (r && r.ok) { ta.value = ""; app.toast(`Steered ${a.name}`, "ok"); } };
    ta.addEventListener("keydown", (ev) => { if (ev.key === "Enter" && !ev.shiftKey) { ev.preventDefault(); send(); } });
    root.addEventListener("click", (ev) => {
      const chip = ev.target.closest(".live-chip"); if (chip) { live.watch(chip.dataset.key); return; }
      const sub = ev.target.closest("[data-sub]"); if (sub) { live.sub = sub.dataset.sub; root.querySelectorAll("[data-sub]").forEach((b) => b.classList.toggle("on", b === sub)); paintStream(); return; }
      const act = ev.target.closest("[data-act]"); if (!act) return;
      const what = act.dataset.act;
      if (what === "steer") send();
      else if (what === "pause") T.command("pause");
      else if (what === "stop") app.confirm(`Stop ${a.name}?`, "It stops at its next tool or model call, its own sub-agents with it; the agent that spawned it gets the stopped hand-back and carries on.", "", () => T.command("stop"));
      else if (what === "follow") T.toggleFollow();
      else if (what === "pin") live.pin(live.pinned === a.key ? "" : a.key);
    });
    paintStream();
  };
  /** A new fleet-live message: the same agent's header and buttons follow (the stream keeps its own pace). */
  let shown = "";
  T.refresh = () => {
    const list = live.byNode[live.card] || [], a = current();
    const sig = JSON.stringify([live.card, list.map((x) => x.key + x.state + x.activity), a && [a.state, a.current, Number(a.cost_usd).toFixed(4)], live.pinned]);
    if (sig === shown && pane()) return;
    shown = sig;
    if (pane()) T.render($("inspector-body"));
  };
})();
