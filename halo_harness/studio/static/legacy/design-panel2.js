/* Halo Studio -- the Design panel, second half (3.0.1.0 round D3): Knobs
   (an artboard's controls.json as sliders, colour inputs and selects,
   debounced 150 ms, applied in place without a model call), System (the
   tokens by group, editable) and Export (folder / html / png / svg / pdf, and
   the handoff bundle). */
(function () {
  "use strict";
  const { h, esc, field } = window.inspector;
  const d = window.designMode;
  const hex = (v) => (/^#[0-9a-fA-F]{6}$/.test(String(v)) ? v : "#000000");

  d.setKnob = async (aid, name, value) => {
    try {
      const r = await d.call("POST", "control", { artboard: aid, name, value });
      if (r.queued) d.toast(`${name} is saved: the next turn applies it`, "ok");
      else d.bust[aid] = (d.bust[aid] || 0) + 1;
      await d.reload(false); if (d.refreshContrast) d.refreshContrast();
    } catch (e) { d.toast((e.data && e.data.problems && e.data.problems[0]) || e.message, "bad"); }
  };
  const boardPicker = (body, withAll, onPick) => {
    const boards = (d.data && d.data.artboards) || [];
    const sel = h(`<select aria-label="Artboard">${withAll ? '<option value="">All artboards</option>' : ""}${boards.map((a) => `<option value="${esc(a.id)}"${a.id === d.selected ? " selected" : ""}>${esc(a.title || a.id)}</option>`).join("")}</select>`);
    sel.addEventListener("change", () => onPick(sel.value)); body.appendChild(field("Artboard", sel)); return sel;
  };

  d.knobsTab = (body) => {
    const D = d.data;
    if (!D || !D.artboards.length) { body.appendChild(h(`<p class="hint">Knobs belong to an artboard. Run a turn first, then ask for knobs: "add knobs for spacing and the accent colour".</p>`)); return; }
    boardPicker(body, false, (id) => { d.selected = id; d.rail(); d.drawCards(); d.showTab("knobs"); });
    const a = d.artboard(d.selected) || D.artboards[0];
    const knobs = a.controls || [];
    if (!knobs.length) { body.appendChild(h(`<p class="hint">${esc(a.title || a.id)} has no knobs yet. Ask for them in a turn: "add knobs for spacing and the accent colour".</p>`)); d.contrastSection(body, a); return; }
    knobs.forEach((k) => {
      let control; const timer = { t: null };
      const send = (v) => { clearTimeout(timer.t); timer.t = setTimeout(() => d.setKnob(a.id, k.name, v), 150); };
      const val = h(`<span class="d-knobval">${esc(k.value)}</span>`);
      if (k.kind === "color") { control = h(`<input type="color" value="${esc(hex(k.value))}" aria-label="${esc(k.name)}">`); control.addEventListener("input", () => { val.textContent = control.value; send(control.value); }); }
      else if (k.kind === "select") { control = h(`<select aria-label="${esc(k.name)}">${(k.options || []).map((o) => `<option${String(o) === String(k.value) ? " selected" : ""}>${esc(o)}</option>`).join("")}</select>`); control.addEventListener("change", () => { val.textContent = control.value; send(control.value); }); }
      else { control = h(`<input type="range" min="${esc(k.min == null ? 0 : k.min)}" max="${esc(k.max == null ? 100 : k.max)}" step="${esc(k.step || 1)}" value="${esc(k.value == null ? 0 : k.value)}" aria-label="${esc(k.name)}">`); control.addEventListener("input", () => { val.textContent = control.value; send(Number(control.value)); }); }
      const row = h(`<div class="d-knob"><div class="d-knobhead"><label>${esc(k.name)}</label></div></div>`);
      row.querySelector(".d-knobhead").appendChild(val); row.appendChild(control);
      row.appendChild(h(`<div class="hint mono">${esc(k.target || "")}${String(k.target || "").startsWith("css:") ? "" : " · applies on the next turn"}</div>`));
      body.appendChild(row);
    });
    d.contrastSection(body, a);
  };

  d.systemTab = (body) => {
    const D = d.data;
    if (!D) { body.appendChild(h(`<p class="hint">Open a project to see its design system.</p>`)); return; }
    const sys = JSON.parse(JSON.stringify(D.system || {})); sys.tokens = sys.tokens || {};
    const groups = Object.entries(sys.tokens);
    if (!groups.length) body.appendChild(h(`<p class="hint">No design system yet. Sync one from a codebase or a URL in the left rail, or ask for tokens in a turn.</p>`));
    groups.forEach(([g, vals]) => {
      body.appendChild(h(`<div class="section-head"><span>${esc(g)}</span><span class="hint">${Object.keys(vals).length}</span></div>`));
      Object.entries(vals).forEach(([name, value]) => {
        const row = h(`<div class="d-token"><code>${esc(name)}</code><input value="${esc(value)}" aria-label="${esc(g)} ${esc(name)}"></div>`);
        const sw = /^#[0-9a-fA-F]{3,8}$/.test(String(value)) ? h(`<i class="d-swatch" style="background:${esc(value)}"></i>`) : null; if (sw) row.insertBefore(sw, row.firstChild);
        row.querySelector("input").addEventListener("input", (ev) => { vals[name] = ev.target.value; sys.tokens[g] = vals; if (sw) sw.style.background = ev.target.value; });
        body.appendChild(row);
      });
    });
    const comps = (sys.components || []).map((c) => (c && c.name) || c);
    if (comps.length) body.append(h(`<div class="section-head"><span>Components</span><span class="hint">${comps.length}</span></div>`), h(`<div class="d-sys">${comps.slice(0, 60).map((c) => `<span class="d-chip">${esc(c)}</span>`).join("")}</div>`));
    if ((sys.sources || []).length) body.append(h(`<div class="section-head"><span>Sources</span></div>`), h(`<ul class="d-src">${sys.sources.map((s) => `<li class="mono">${esc(s)}</li>`).join("")}</ul>`));
    const save = h(`<button class="btn primary"${groups.length ? "" : " disabled"}>Save tokens</button>`);
    save.addEventListener("click", async () => { try { await d.call("PUT", "system", { system: sys }); await d.reload(false); d.toast("Design system saved", "ok"); } catch (e) { d.toast(e.message, "bad"); } });
    body.appendChild(h(`<div class="d-sendrow"></div>`)).appendChild(save);
  };

  d.exportAs = async (kind) => {
    if (!d.slug) { d.toast("Open a project first", "warn"); return; }
    try {
      const sel = document.getElementById("d-export-board");
      const r = await d.call("POST", "export", { as: kind, artboard: sel ? sel.value : "" });
      d.exportLines = r.lines; d.toast(`Export ${kind}: ${r.lines.length} line(s)`, "ok");
      if (d.tab !== "export") d.showTab("export"); else paintLines();
    } catch (e) { d.toast(e.message, "bad"); }
  };
  d.handoff = async () => {
    if (!d.slug) { d.toast("Open a project first", "warn"); return; }
    try { d.handoffPath = (await d.call("POST", "handoff", {})).path; d.toast("Handoff bundle written", "ok"); if (d.tab !== "export") d.showTab("export"); else paintLines(); } catch (e) { d.toast(e.message, "bad"); }
  };
  function paintLines() {
    const box = document.getElementById("d-export-out"); if (!box) return;
    box.innerHTML = (d.exportLines.length ? `<pre class="pc-log">${esc(d.exportLines.join("\n"))}</pre>` : "")
      + (d.handoffPath ? `<div class="d-handoff"><span class="mono">${esc(d.handoffPath)}</span><button class="btn ghost" id="d-copy">Copy</button></div><p class="hint">Start the next session there: <code>halo --cwd "${esc(d.handoffPath)}" "continue from HANDOFF.md"</code></p>` : "");
    const c = document.getElementById("d-copy");
    if (c) c.onclick = async () => { try { await navigator.clipboard.writeText(d.handoffPath); d.toast("Path copied", "ok"); } catch (e) { d.toast("Copy failed: select the path and copy it", "warn"); } };
  }
  d.exportTab = (body) => {
    if (!d.data) { body.appendChild(h(`<p class="hint">Open a project to export it.</p>`)); return; }
    boardPicker(body, true, () => {}).id = "d-export-board";
    const row = h(`<div class="d-exports"></div>`);
    [["folder", "Folder (a shareable site)"], ["html", "HTML"], ["png", "PNG"], ["svg", "SVG"], ["pdf", "PDF"]].forEach(([k, l]) => { const b = h(`<button class="btn">${l}</button>`); b.addEventListener("click", () => d.exportAs(k)); row.appendChild(b); });
    body.appendChild(row);
    const ho = h(`<button class="btn primary">Handoff bundle</button>`); ho.addEventListener("click", d.handoff);
    body.append(h(`<div class="section-head"><span>Handoff</span></div>`), h(`<p class="hint">A folder with the artboards, the design system and HANDOFF.md for the next Halo or Claude Code session.</p>`), ho, h(`<div id="d-export-out"></div>`));
    paintLines();
  };
})();
