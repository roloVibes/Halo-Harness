/* Halo Studio -- the Design panel, first half (3.0.1.0 round D3): the Chat
   tab (prompt box, model override, the turn's streaming events as cards, the
   project's running cost, the history) and the Comments tab (open pins by
   artboard, Resolve, Send comments). Knobs, System and Export are in
   design-panel2.js. */
(function () {
  "use strict";
  const { h, esc } = window.inspector;
  const d = window.designMode;
  const money = (n) => (n == null ? "?" : "$" + Number(n).toFixed(4).replace(/0{1,2}$/, ""));

  function eventCard(ev) {
    if (ev.type === "assistant") {
      return ((ev.message && ev.message.content) || []).map((b) => {
        if (b.type === "text" && b.text) return `<div class="d-ev prose">${esc(b.text)}</div>`;
        if (b.type === "tool_use") return `<div class="d-ev tool"><b>${esc(b.name || "tool")}</b><code>${esc(JSON.stringify(b.input || {}).slice(0, 80))}</code></div>`;
        return "";
      }).join("");
    }
    if (ev.type === "result") return `<div class="d-ev result"><b>result</b>${ev.total_cost_usd != null || ev.cost_usd != null ? `<span>${money(ev.total_cost_usd != null ? ev.total_cost_usd : ev.cost_usd)}</span>` : ""}${typeof ev.result === "string" ? `<div class="prose">${esc(ev.result)}</div>` : ""}</div>`;
    if (ev.type === "halo_design") return `<div class="d-ev done">turn finished: ${(ev.versions || []).map((v) => esc(v[0]) + " v" + v[1]).join(", ") || "no artboard changed"} · exit ${esc(ev.code)} · ${money(ev.cost)}</div>`;
    if (ev.type === "stdout") return `<div class="d-ev raw">${esc(ev.text)}</div>`;
    return "";
  }
  d.paintEvents = () => {
    const box = document.getElementById("d-events"); if (!box || !d.turn) return;
    const stick = box.scrollTop + box.clientHeight >= box.scrollHeight - 24;
    box.innerHTML = `<div class="d-ev user"><b>you</b><div class="prose">${esc(d.turn.prompt)}</div></div>` + d.turn.events.map(eventCard).join("")
      + (d.turn.done ? "" : `<div class="d-ev live"><span class="d-dots"><i></i><i></i><i></i></span> working…</div>`);
    if (stick) box.scrollTop = box.scrollHeight;
    const run = document.getElementById("d-run"); if (run) { run.disabled = d.live(); run.textContent = d.live() ? "Running…" : "Run turn"; }
  };

  d.chatTab = (body) => {
    const D = d.data;
    if (!D) { body.appendChild(h(`<p class="hint">Create or open a project in the left rail, then describe what to design here.</p>`)); return; }
    const hist = D.history || [];
    body.appendChild(h(`<div class="section-head"><span>${esc(D.meta.name)}</span><span class="d-cost" title="Sum of every turn's cost">$${d.spent().toFixed(3)} · ${hist.length} turn(s)</span></div>`));
    const prompt = h(`<textarea class="d-prompt" rows="5" aria-label="Design prompt" placeholder="Describe what to make or change. Enter sends, Shift+Enter adds a line."></textarea>`);
    prompt.value = d.draft || "";
    const model = d.modelSelect(""); model.options[0].textContent = `(project model: ${(D.meta.model || "default")})`;
    const budget = h(`<input type="number" min="0" step="0.5" placeholder="max $" aria-label="Budget in US dollars" class="d-budget">`);
    const run = h(`<button class="btn primary" id="d-run">Run turn</button>`);
    const go = async () => {
      const text = prompt.value.trim(); if (!text || d.live()) return;
      d.draft = ""; prompt.value = "";
      await d.runTurn(text, { model: model.value, budget: parseFloat(budget.value) || undefined });
    };
    prompt.addEventListener("input", () => { d.draft = prompt.value; });
    prompt.addEventListener("keydown", (ev) => { if (ev.key === "Enter" && !ev.shiftKey && !ev.isComposing) { ev.preventDefault(); go(); } });
    run.addEventListener("click", go);
    const row = h(`<div class="d-runrow"></div>`); row.append(model, budget, run);
    body.append(prompt, row, h(`<div id="d-events" class="d-events" aria-live="polite"></div>`));
    if (!D.artboards.length && !d.turn) body.appendChild(h(`<div class="hint">Try: ${d.suggestions.map((s, i) => `<button class="btn ghost d-sugg" data-i="${i}">${esc(s.slice(0, 44))}…</button>`).join(" ")}</div>`));
    body.querySelectorAll(".d-sugg").forEach((b) => b.addEventListener("click", () => { prompt.value = d.draft = d.suggestions[Number(b.dataset.i)]; prompt.focus(); }));
    if (d.turn) d.paintEvents();
    body.appendChild(h(`<div class="section-head"><span>History</span><span class="hint">${hist.length}</span></div>`));
    if (!hist.length) body.appendChild(h(`<p class="hint">Every turn lands here with its cost and the versions it made.</p>`));
    hist.slice().reverse().slice(0, 40).forEach((x) => body.appendChild(h(`<div class="d-hist" title="${esc(x.prompt)}"><div class="prose">${esc((x.prompt || "").slice(0, 160))}</div><small>${esc(x.ts || "")} · ${money(x.cost)} · ${esc((x.versions || []).map((v) => v[0] + " v" + v[1]).join(", ") || "no change")}${x.code ? " · exit " + esc(x.code) : ""}</small></div>`)));
  };

  d.commentsTab = (body) => {
    const D = d.data;
    if (!D) { body.appendChild(h(`<p class="hint">Open a project to see its comments.</p>`)); return; }
    const open = d.openComments(), done = (D.comments || []).length - open.length;
    body.appendChild(h(`<div class="section-head"><span>Open comments</span><span class="hint">${open.length}${done ? " · " + done + " resolved" : ""}</span></div>`));
    if (!open.length) body.appendChild(h(`<p class="hint">Turn on the Comment tool (C) and click a frame to pin a note. Send comments turns every open pin into one prompt.</p>`));
    D.artboards.forEach((a) => {
      const mine = open.filter((c) => c.artboard === a.id); if (!mine.length) return;
      body.appendChild(h(`<div class="d-group"><b>${esc(a.title || a.id)}</b> <small>${esc(a.id)} · v${a.latest}</small></div>`));
      mine.forEach((c, i) => {
        const row = h(`<div class="d-comment"><span class="d-pin sm">${i + 1}</span><div><div class="prose">${esc(c.text)}</div><small>${Math.round(c.x)}%, ${Math.round(c.y)}%${c.path ? " · " + esc(c.path) : ""} · on v${c.version || "?"}</small></div><button class="btn ghost">Resolve</button></div>`);
        row.querySelector("button").addEventListener("click", async () => { await d.call("POST", "comments/resolve", { ids: [c.id] }); await d.reload(true); });
        row.addEventListener("mouseenter", () => d.centerOn(a.id)); body.appendChild(row);
      });
    });
    const send = h(`<button class="btn primary" id="d-send"${open.length && !d.live() ? "" : " disabled"}>Send comments${open.length ? " (" + open.length + ")" : ""}</button>`);
    send.addEventListener("click", async () => { d.showTab("comments"); await d.sendComments(); });
    body.appendChild(h(`<div class="d-sendrow"></div>`)).appendChild(send);
    body.appendChild(h(`<p class="hint">Runs one turn with: "Address these comments: …" and resolves the pins when it succeeds.</p>`));
  };
})();
