/* Halo Studio -- Design mode, the "plus more" half (3.0.1.0 round D5):
   Explore N directions (the variants turn and the tiling after it), the
   critique turn, the Contrast table in the Knobs tab, and every Design
   shortcut with its command-palette entry. Assets are design-assets.js. */
(function () {
  "use strict";
  const { h, esc } = window.inspector;
  const $ = (id) => document.getElementById(id);
  const d = window.designMode;
  const posKey = () => "halo-design-pos:" + d.slug;

  // -- Explore N directions ---------------------------------------------------------------
  d.variants = (n = 3, opts = {}) => {
    const prompt = (opts.prompt || d.draft || "").trim();
    if (!prompt) { d.showTab("chat"); const p = document.querySelector(".d-prompt"); if (p) p.focus(); d.toast("Write what to design, then explore directions", "warn"); return null; }
    d.draft = "";
    return d.runTurn(prompt, { model: opts.model, budget: opts.budget, variants: n, base: opts.base || d.selected || "direction" });
  };
  d.tileNew = (before) => {  // the new artboards in one row to the right of the old ones; the first is selected
    const fresh = ((d.data && d.data.artboards) || []).filter((a) => !before.includes(a.id));
    if (!fresh.length) return;
    const cards = [...document.querySelectorAll("#design-world .d-card")];
    const old = cards.filter((k) => before.includes(k.dataset.id));
    let x = old.length ? Math.max(...old.map((k) => k.offsetLeft + k.offsetWidth)) + 64 : 40;
    let saved = {}; try { saved = JSON.parse(localStorage.getItem(posKey()) || "{}"); } catch (e) {}
    fresh.forEach((a) => {
      const k = cards.find((c) => c.dataset.id === a.id); if (!k) return;
      k.style.left = x + "px"; k.style.top = "40px"; saved[a.id] = { x, y: 40 }; x += k.offsetWidth + 48;
    });
    try { localStorage.setItem(posKey(), JSON.stringify(saved)); } catch (e) {}
    d.selected = fresh[0].id; d.rail(); d.drawCards(); d.fit(); if (d.tab === "knobs" || d.tab === "export") d.showTab(d.tab);
  };

  // -- critique ------------------------------------------------------------------------------
  d.critique = async (aid, model) => {
    aid = aid || d.selected;
    if (!d.slug || !aid) { d.toast("Select an artboard to critique first", "warn"); return null; }
    if (d.live()) { d.toast("A turn is already running in this project", "warn"); return null; }
    try {
      const r = await d.call("POST", "critique", { artboard: aid, model: model || undefined });
      const done = await d.attach(r.turn, `Critique of ${aid}: a second model reads the artboard and pins its notes`);
      if (done) { d.toast(done.note || "Critique finished", done.pins && done.pins.length ? "ok" : "warn"); d.showTab("comments"); }
      return done;
    } catch (e) { d.toast(e.message, "bad"); return null; }
  };

  // -- contrast ----------------------------------------------------------------------------------
  const dot = (p) => (p.aa ? "ok" : p.aa_large ? "warn" : "bad");
  d.refreshContrast = async () => {
    const box = $("d-contrast"); if (!box || !d.slug) return;
    try {
      const r = await d.call("GET", `artboard/${encodeURIComponent(box.dataset.id)}/contrast`);
      const rows = r.pairs.map((p) => `<tr><td><i class="d-dot ${dot(p)}" title="${p.aa ? (p.aaa ? "AAA" : "AA") : p.aa_large ? "large text only" : "fails"}"></i></td><td><i class="d-swatch" style="background:${esc(p.fg_value)}"></i> <code>${esc(p.fg)}</code></td><td><i class="d-swatch" style="background:${esc(p.bg_value)}"></i> <code>${esc(p.bg)}</code></td><td class="num">${p.ratio.toFixed(2)}</td><td>${p.aaa ? "AAA" : p.aa ? "AA" : p.aa_large ? "large" : "fail"}</td></tr>`).join("");
      box.innerHTML = (rows ? `<table class="d-contrast"><thead><tr><th></th><th>text</th><th>on</th><th>ratio</th><th></th></tr></thead><tbody>${rows}</tbody></table>` : "") + `<p class="hint">${esc(r.note)}</p>`;
    } catch (e) { box.innerHTML = `<p class="hint">${esc(e.message)}</p>`; }
  };
  d.contrastSection = (body, a) => {
    body.append(h(`<div class="section-head"><span>Contrast</span><span class="hint">WCAG, refreshes after a knob moves</span></div>`), h(`<div id="d-contrast" data-id="${esc(a.id)}"><p class="hint">checking…</p></div>`));
    d.refreshContrast();
  };

  // -- shortcuts and the palette ---------------------------------------------------------------
  const prompt = () => { d.showTab("chat"); const p = document.querySelector(".d-prompt"); if (p) p.focus(); };
  const ACTIONS = [  // [key, label, run]: none collides with the global R / O / D / ? / A / [ / ] or Ctrl+K
    ["n", "New project", () => d.openNew()], ["Enter", "Run a turn (Enter in the Chat box)", prompt],
    ["c", "Toggle the comment tool", () => d.setTool(d.tool === "comment" ? "select" : "comment")],
    ["v", "Explore 3 directions of the Chat prompt", () => d.variants(3)], ["k", "Critique the selected artboard", () => d.critique()],
    ["x", "Check contrast of the selected artboard", () => d.showTab("knobs")], ["s", "Send comments", () => d.sendComments()],
    ["y", "Sync design system", () => { const i = $("d-sync-src"); if (i) i.focus(); }], ["u", "Add assets", () => d.pickAssets && d.pickAssets()],
    ["e", "Export folder", () => d.exportAs("folder")], ["h", "Handoff bundle", () => d.handoff()], ["f", "Fit canvas", () => d.fit()],
  ];
  d.key = (ev) => {
    if (ev.ctrlKey || ev.metaKey || ev.altKey) return false;
    const t = document.activeElement;
    if (t && (/^(INPUT|TEXTAREA|SELECT)$/.test(t.tagName) || t.isContentEditable)) return false;  // never while typing
    if (ev.key === "Escape") { d.setTool("select"); return false; }
    const hit = ev.key.length === 1 && ACTIONS.find((a) => a[0] === ev.key.toLowerCase());
    if (hit) { ev.preventDefault(); hit[2](); return true; }
    return ev.key === "a" || ev.key === "Delete" || ev.key === "Backspace";
  };
  d.commands = () => ACTIONS.map(([key, label, run]) => ({ label: "Design: " + label, key: key.length === 1 ? key.toUpperCase() : key, run }));
})();
