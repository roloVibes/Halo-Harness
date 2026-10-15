"""halo_harness.fleet.recording_page -- the page of a flight recording (Halo
3.0.5.0 "Fleet" round R4): one HTML file with its CSS and JS inline and the
session as a JSON block, so it opens anywhere with no network at all.
recording.py fills it. The page draws: the header (session, harness, start,
length, cost), Play / Pause with a speed, the scrub bar, one lane per agent
(bars coloured by state, a tick per tool call, the cursor), the cost curve,
the agent list and the selected agent's three streams (Thinking, Working,
Output) as they were at the cursor. Space plays or pauses, Left / Right
step, 1 2 3 pick the stream."""

CSS = r"""
:root { --bg: #070b12; --panel: #0d1420; --line: #1f2b3d; --text: #d8e4f2; --muted: #7d8da3; --accent: #39d0ff;
  --warn: #ffb547; --ok: #4fe3a1; --bad: #ff5d73; --mono: ui-monospace, "Cascadia Code", Menlo, Consolas, monospace;
  --sans: system-ui, -apple-system, "Segoe UI", Roboto, sans-serif; }
* { box-sizing: border-box; }
body { margin: 0; background: var(--bg); color: var(--text); font: 14px/1.45 var(--sans); }
header { padding: 18px 24px 8px; border-bottom: 1px solid var(--line); }
.kick { font: 600 11px var(--mono); letter-spacing: .14em; color: var(--accent); }
h1 { margin: 4px 0 2px; font-size: 20px; }
.mono { font-family: var(--mono); }
.muted { color: var(--muted); }
.bar { display: flex; gap: 10px; align-items: center; padding: 10px 24px; position: sticky; top: 0; background: var(--bg); z-index: 2; border-bottom: 1px solid var(--line); }
button, select { background: var(--panel); color: var(--text); border: 1px solid var(--line); border-radius: 6px; padding: 5px 12px; font: inherit; cursor: pointer; }
button.on { border-color: var(--accent); color: var(--accent); }
#scrub { flex: 1; accent-color: var(--accent); }
#lanes { padding: 10px 24px 4px; display: grid; gap: 4px; }
.lane { display: grid; grid-template-columns: 170px 1fr; gap: 10px; align-items: center; cursor: pointer; }
.lane-name { font: 12px var(--mono); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.lane.on .lane-name { color: var(--accent); }
.track { position: relative; height: 16px; background: var(--panel); border: 1px solid var(--line); border-radius: 4px; overflow: hidden; }
.seg { position: absolute; top: 0; bottom: 0; opacity: .85; }
.seg[data-a="typing"] { background: color-mix(in srgb, var(--accent) 55%, transparent); }
.seg[data-a="tool"] { background: var(--accent); }
.seg[data-a="waiting"] { background: var(--warn); }
.seg[data-a="done"] { background: color-mix(in srgb, var(--ok) 30%, transparent); }
.seg[data-a="failed"] { background: var(--bad); }
.tick { position: absolute; top: 0; width: 2px; height: 100%; background: #fff; opacity: .7; }
.cursor { position: absolute; top: -2px; bottom: -2px; width: 2px; background: var(--warn); box-shadow: 0 0 6px var(--warn); }
#cost { padding: 4px 24px 8px 204px; }
#cost svg { width: 100%; height: 54px; display: block; background: var(--panel); border: 1px solid var(--line); border-radius: 4px; }
#cost polyline { fill: none; stroke: var(--ok); stroke-width: 2; vector-effect: non-scaling-stroke; }
#cost line { stroke: var(--warn); stroke-width: 2; vector-effect: non-scaling-stroke; }
main { display: grid; grid-template-columns: 220px 1fr; gap: 16px; padding: 8px 24px 32px; }
#agents { display: grid; gap: 4px; align-content: start; }
.agent { text-align: left; display: grid; gap: 1px; }
.agent small { color: var(--muted); font: 11px var(--mono); }
.agent.on { border-color: var(--accent); }
.streams { min-width: 0; }
#tabs { display: flex; gap: 6px; margin-bottom: 8px; }
#stream { border: 1px solid var(--line); border-radius: 8px; background: var(--panel); padding: 10px 14px; min-height: 200px; max-height: 60vh; overflow: auto; }
.row { margin: 0 0 8px; white-space: pre-wrap; overflow-wrap: anywhere; }
.row b { font: 600 10px var(--mono); letter-spacing: .1em; color: var(--muted); text-transform: uppercase; margin-right: 6px; }
.row[data-k="thinking"] { color: var(--muted); font-style: italic; }
.row[data-k="user"] { border-left: 2px solid var(--accent); padding-left: 8px; }
.tool { border: 1px solid var(--line); border-radius: 6px; padding: 5px 8px; margin: 0 0 6px; }
.tool .lbl { font: 12px var(--mono); }
.tool pre { margin: 4px 0 0; font: 11px var(--mono); color: var(--muted); white-space: pre-wrap; max-height: 140px; overflow: auto; }
.tool[data-s="error"] { border-color: var(--bad); }
.tool[data-s="running"] { border-color: var(--accent); }
.empty { color: var(--muted); }
"""

JS = r"""
(function () {
  "use strict";
  var D = JSON.parse(document.getElementById("data").textContent);
  var $ = function (id) { return document.getElementById(id); };
  var t0 = Number(D.started) || 0, t1 = Math.max(Number(D.ended) || t0, t0 + 1), span = t1 - t0;
  var cur = t1, sel = D.focus || (D.agents[0] && D.agents[0].agent_id) || "main", tab = "thinking";
  var playing = false, speed = 10, last = 0;
  function esc(s) { return String(s == null ? "" : s).replace(/[&<>"]/g, function (c) { return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]; }); }
  function len(s) { s = Math.max(0, Math.round(s)); var m = Math.floor(s / 60); return (m ? m + "m " : "") + (s % 60) + "s"; }
  function money(v) { return "$" + (Number(v) || 0).toFixed(4); }
  function pct(t) { return Math.max(0, Math.min(100, (t - t0) / span * 100)); }
  function stamp(t) { var d = new Date(t * 1000); return d.toLocaleString(); }
  document.title = "Recording: " + (D.title || D.session_id);
  $("title").textContent = D.title || D.session_id;
  $("meta").textContent = [D.harness, D.session_id, D.started ? stamp(D.started) : "", len(span), money(D.cost_usd)].filter(Boolean).join(" · ");
  var byAgent = {};
  D.states.forEach(function (s) { (byAgent[s.agent_id] = byAgent[s.agent_id] || []).push(s); });
  function lanes() {
    $("lanes").innerHTML = D.agents.map(function (a) {
      var st = byAgent[a.agent_id] || [], segs = "";
      for (var i = 0; i < st.length; i++) {
        var from = st[i].t, to = i + 1 < st.length ? st[i + 1].t : (st[i].activity === "done" || st[i].activity === "failed" ? from + span / 200 : t1);
        segs += '<div class="seg" data-a="' + esc(st[i].activity) + '" style="left:' + pct(from) + '%;width:' + Math.max(0.3, pct(to) - pct(from)) + '%" title="' + esc(st[i].activity + (st[i].tool ? " " + st[i].tool : "")) + '"></div>';
      }
      var ticks = (D.entries[a.agent_id] || []).filter(function (e) { return (e.kind === "tool_call" || e.kind === "spawn") && e.ts; })
        .map(function (e) { return '<div class="tick" style="left:' + pct(e.ts) + '%" title="' + esc(e.label || e.name) + '"></div>'; }).join("");
      return '<div class="lane' + (a.agent_id === sel ? " on" : "") + '" data-id="' + esc(a.agent_id) + '"><span class="lane-name">' + esc(a.name) + (a.role && a.role !== a.name ? " · " + esc(a.role) : "") + '</span><div class="track">' + segs + ticks + '<div class="cursor"></div></div></div>';
    }).join("");
  }
  function costCurve() {
    var pts = [[t0, 0]].concat(D.costs.map(function (c) { return [c.t, c.usd]; })), top = Math.max(0.0001, Number(D.cost_usd) || 0);
    var poly = pts.map(function (p) { return (pct(p[0]) * 10).toFixed(1) + "," + (58 - p[1] / top * 54).toFixed(1); }).join(" ");
    $("cost").innerHTML = '<svg viewBox="0 0 1000 60" preserveAspectRatio="none" role="img" aria-label="cost over time"><polyline points="' + poly + '"></polyline><line id="costline" x1="0" x2="0" y1="0" y2="60"></line></svg>';
  }
  function agentsList() {
    $("agents").innerHTML = D.agents.map(function (a) {
      return '<button class="agent' + (a.agent_id === sel ? " on" : "") + '" data-id="' + esc(a.agent_id) + '"><span>' + esc(a.name) + '</span><small>' + esc(a.state) + " · " + money(a.cost_usd) + (a.model ? " · " + esc(a.model) : "") + '</small></button>';
    }).join("");
  }
  function upto() { return (D.entries[sel] || []).filter(function (e) { return !e.ts || e.ts <= cur + 0.001; }); }
  function stream() {
    var es = upto(), html = "";
    if (tab === "working") {
      var res = {}; es.forEach(function (e) { if (e.kind === "tool_result" && e.id) res[e.id] = e; });
      html = es.filter(function (e) { return e.kind === "tool_call" || e.kind === "spawn"; }).map(function (e) {
        var r = res[e.id], s = r ? (r.is_error ? "error" : "done") : "running";
        return '<div class="tool" data-s="' + s + '"><div class="lbl">' + esc(e.kind === "spawn" ? e.name + ": " + (e.task || "") : e.label || e.name) + ' <span class="muted">' + s + '</span></div>' + (r && r.text ? "<pre>" + esc(String(r.text).split("\n").slice(0, 12).join("\n")) + "</pre>" : "") + "</div>";
      }).join("");
    } else if (tab === "output") {
      var hand = es.filter(function (e) { return e.kind === "handback"; }).pop(), out = [];
      if (!hand) for (var i = es.length - 1; i >= 0; i--) { if (es[i].kind === "text") out.unshift(es[i].text || ""); else if (["tool_call", "spawn", "user"].indexOf(es[i].kind) >= 0) break; }
      var text = hand ? hand.text : out.join("");
      html = text ? '<div class="row">' + esc(text) + "</div>" : "";
    } else {
      html = es.filter(function (e) { return ["text", "thinking", "user", "note", "control", "ask", "error", "handback"].indexOf(e.kind) >= 0; }).map(function (e) {
        var who = e.kind === "control" ? (e.cmd || "control") + (e.by ? " by " + e.by : "") : e.kind;
        return '<div class="row" data-k="' + esc(e.kind) + '"><b>' + esc(who) + "</b>" + esc(e.text || e.what || e.reason || "") + "</div>";
      }).join("");
    }
    $("stream").innerHTML = html || '<p class="empty">Nothing here yet at this point of the recording.</p>';
    $("stream").scrollTop = $("stream").scrollHeight;
  }
  function paint() {
    var p = pct(cur);
    document.querySelectorAll(".cursor").forEach(function (c) { c.style.left = p + "%"; });
    var cl = document.getElementById("costline"); if (cl) { cl.setAttribute("x1", p * 10); cl.setAttribute("x2", p * 10); }
    $("scrub").value = Math.round(p * 10);
    $("clock").textContent = len(cur - t0) + " / " + len(span);
    stream();
  }
  function select(id) { sel = id; lanes(); agentsList(); paint(); }
  function step(now) {
    if (!playing) return;
    if (last) cur = Math.min(t1, cur + (now - last) / 1000 * speed);
    last = now;
    paint();
    if (cur >= t1) { playing = false; $("play").textContent = "Play"; return; }
    requestAnimationFrame(step);
  }
  function toggle() {
    playing = !playing; last = 0; $("play").textContent = playing ? "Pause" : "Play";
    if (playing) { if (cur >= t1) cur = t0; requestAnimationFrame(step); }
  }
  $("play").addEventListener("click", toggle);
  $("speed").addEventListener("change", function () { speed = Number($("speed").value) || 1; });
  $("scrub").addEventListener("input", function () { cur = t0 + span * Number($("scrub").value) / 1000; paint(); });
  document.addEventListener("click", function (ev) {
    var hit = ev.target.closest(".lane, .agent"); if (hit) { select(hit.dataset.id); return; }
    var b = ev.target.closest("#tabs button"); if (!b) return;
    tab = b.dataset.tab; document.querySelectorAll("#tabs button").forEach(function (x) { x.classList.toggle("on", x === b); }); stream();
  });
  document.addEventListener("keydown", function (ev) {
    if (ev.target.tagName === "SELECT") return;
    if (ev.key === " ") { ev.preventDefault(); toggle(); }
    else if (ev.key === "ArrowLeft" || ev.key === "ArrowRight") { cur = Math.max(t0, Math.min(t1, cur + (ev.key === "ArrowLeft" ? -1 : 1) * span / 100)); paint(); }
    else if ("123".indexOf(ev.key) >= 0 && ev.key) { var bs = document.querySelectorAll("#tabs button"); bs[Number(ev.key) - 1].click(); }
  });
  lanes(); costCurve(); agentsList(); paint();
})();
"""

BODY = """<header><div class="kick">HALO FLIGHT RECORDING</div><h1 id="title"></h1><div id="meta" class="mono muted"></div></header>
<section class="bar"><button id="play">Play</button>
<select id="speed" aria-label="speed"><option value="1">1x</option><option value="10" selected>10x</option><option value="60">60x</option></select>
<input type="range" id="scrub" min="0" max="1000" value="1000" aria-label="scrub"><span id="clock" class="mono muted"></span></section>
<section id="lanes" aria-label="one lane per agent"></section>
<section id="cost" aria-label="the cost curve"></section>
<main><aside id="agents" aria-label="agents"></aside>
<div class="streams"><nav id="tabs"><button data-tab="thinking" class="on">Thinking</button><button data-tab="working">Working</button><button data-tab="output">Output</button></nav>
<div id="stream"></div></div></main>
"""
