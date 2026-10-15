/* Halo Studio -- canvas replay (3.0.5.0 R4, D12). A finished session played
   back on the Roles (or Org) canvas: the shell posts {type: "fleet-replay",
   events, meta} (routes/fleet/replay.ts, from GET /api/fleet/replay: the
   session's agents and their state changes in time order) and this page
   draws a scrub bar along the bottom of the canvas -- play / pause, the
   speed, the scrub, the clock and the session's cost so far -- and lights
   the cards the way Live Roles does (live.js decorates them), in the order
   the agents worked: a card glows while its agent runs, turns amber while
   it waits, sweeps green when it finishes. While a replay runs live.js keeps
   the shell's fleet-live messages aside; closing the bar (x or Esc) goes
   back to what runs now. The Live tab's history rows (live-tab.js) ask the
   shell for a replay with {type: "fleet-replay-open", session, harness}. */
(function () {
  "use strict";
  if (!/[?&]embedded=1\b/.test(location.search)) return;
  const live = window.haloLive, app = window.app;
  if (!live || !app || !app.canvas) return;
  const esc = window.inspector.esc;
  const SPEEDS = [1, 10, 60, 240, 960];
  const R = window.haloReplay = { on: false, events: [], meta: null, t: 0, t0: 0, t1: 1, speed: 60, playing: false, timer: 0 };
  let bar = null;

  const mmss = (s) => { s = Math.max(0, Math.round(s)); const h = Math.floor(s / 3600), m = Math.floor((s % 3600) / 60), x = s % 60; return (h ? h + ":" + String(m).padStart(2, "0") : m) + ":" + String(x).padStart(2, "0"); };
  function costAt(t) { let usd = 0; for (const c of (R.meta && R.meta.costs) || []) { if (c.t > t) break; usd = Number(c.usd) || 0; } return usd; }

  /** Every agent that had started by `t`, as the rows live.js lights: its state and activity then. */
  function agentsAt(t) {
    const m = R.meta, out = [];
    for (const a of m.agents || []) {
      let last = null, calls = 0;
      for (const e of R.events) { if (e.t > t) break; if (e.agent_id !== a.agent_id) continue; last = e; if (e.activity === "tool") calls += 1; }
      if (!last) continue;
      const ended = last.state === "done" || last.state === "failed";
      out.push({ key: `replay|${m.session_id}|${a.agent_id}`, harness: m.harness || "", local: true, session: m.title || "", session_id: m.session_id, agent_id: a.agent_id,
        parent: a.parent || null, name: a.name || a.agent_id, role: a.role || "", bio: a.bio || "", lineup: a.lineup || "", model: a.model || "", state: last.state,
        task: a.task || "", current: last.tool || "", last_text: "", cost_usd: ended ? Number(a.cost_usd) || 0 : 0, since: 0,
        activity: last.activity || (last.state === "running" ? "typing" : last.state), tool: last.tool || "", calls, control: "none" });
    }
    return out;
  }

  function paint() {
    if (!R.on) return;
    live.agents = agentsAt(R.t);
    live.decorate(app.canvas);
    if (!bar) return;
    const span = Math.max(1, R.t1 - R.t0), lit = live.agents.filter((a) => a.state === "running" || a.state === "waiting");
    bar.querySelector('[data-act="scrub"]').value = String(Math.round(((R.t - R.t0) / span) * 1000));
    bar.querySelector(".replay-clock").textContent = `${mmss(R.t - R.t0)} / ${mmss(span)}`;
    bar.querySelector(".replay-cost").textContent = "$" + costAt(R.t).toFixed(4);
    bar.querySelector(".replay-lit").textContent = lit.length ? lit.map((a) => `${a.name} ${a.state === "waiting" ? "waits" : "works"}`).join(" · ") : "nobody works right now";
    bar.querySelector('[data-act="play"]').textContent = R.playing ? "❚❚" : "▶";
    bar.dataset.t = String(Math.round(R.t - R.t0));
    bar.dataset.lit = lit.map((a) => a.name).join(",");
  }

  function play(on) {
    R.playing = on;
    clearInterval(R.timer);
    if (on) {
      if (R.t >= R.t1) R.t = R.t0;
      R.timer = setInterval(() => { R.t = Math.min(R.t1, R.t + 0.1 * R.speed); if (R.t >= R.t1) play(false); paint(); }, 100);
    }
    paint();
  }

  function close() {
    if (!R.on) return;
    play(false);
    R.on = false; live.replaying = false;
    if (bar) bar.remove();
    bar = null;
    const held = live.held; live.held = null;
    live.agents = held && Array.isArray(held.agents) ? held.agents : [];
    live.decorate(app.canvas);
  }
  R.close = close;

  function build() {
    if (bar) bar.remove();
    const m = R.meta, host = ($("timeline") || document.body).parentNode;
    bar = document.createElement("div");
    bar.id = "replay-bar"; bar.setAttribute("data-testid", "replay-bar"); bar.setAttribute("role", "group"); bar.setAttribute("aria-label", "Replay");
    bar.innerHTML = `<button class="btn primary replay-play" data-act="play" title="Play / pause">▶</button>`
      + `<select data-act="speed" title="Speed">${SPEEDS.map((s) => `<option value="${s}"${s === R.speed ? " selected" : ""}>${s}×</option>`).join("")}</select>`
      + `<div class="replay-mid"><div class="replay-line"><b>Replay</b> <span class="replay-title">${esc(m.title || m.session_id)}</span> <span class="hint mono">${esc(m.harness || "")}</span><span class="replay-clock mono"></span><span class="replay-cost mono"></span></div>`
      + `<input type="range" min="0" max="1000" value="0" data-act="scrub" data-testid="replay-scrub" aria-label="Scrub"><div class="replay-lit hint"></div></div>`
      + `<button class="btn ghost replay-close" data-act="close" title="Back to what runs now (Esc)" data-testid="replay-close">×</button>`;
    host.appendChild(bar);
    bar.addEventListener("click", (ev) => { const b = ev.target.closest("[data-act]"); if (!b) return; if (b.dataset.act === "play") play(!R.playing); else if (b.dataset.act === "close") close(); });
    bar.querySelector('[data-act="speed"]').addEventListener("change", (ev) => { R.speed = Number(ev.target.value) || 60; });
    bar.querySelector('[data-act="scrub"]').addEventListener("input", (ev) => { const v = Number(ev.target.value) / 1000; play(false); R.t = R.t0 + v * (R.t1 - R.t0); paint(); });
  }
  const $ = (id) => document.getElementById(id);

  function start(events, meta) {
    const list = (Array.isArray(events) ? events : []).filter((e) => e && typeof e.t === "number" && e.agent_id).sort((a, b) => a.t - b.t);
    if (!list.length || !meta) return;
    if (!R.on) live.held = { agents: live.agents, pinned: live.pinned };
    R.on = true; live.replaying = true; live.ready = true;
    R.events = list; R.meta = meta;
    R.t0 = Math.min(Number(meta.started) || list[0].t, list[0].t);
    R.t1 = Math.max(Number(meta.ended) || 0, list[list.length - 1].t, R.t0 + 1);
    R.t = R.t0;
    R.speed = SPEEDS.find((s) => (R.t1 - R.t0) / s <= 40) || SPEEDS[SPEEDS.length - 1];
    build();
    play(true);
  }

  window.addEventListener("message", (e) => {
    if (e.origin !== location.origin || e.source !== window.parent || !e.data || e.data.type !== "fleet-replay") return;
    start(e.data.events, e.data.meta);
  });
  window.addEventListener("keydown", (ev) => {
    if (!R.on || ev.key !== "Escape" || /^(INPUT|TEXTAREA|SELECT)$/.test((document.activeElement || {}).tagName || "")) return;
    ev.preventDefault(); ev.stopImmediatePropagation(); close();
  }, true);
})();
