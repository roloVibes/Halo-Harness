/* Halo Studio -- the command palette (Ctrl/Cmd+K) and the first-run tour. */
(function () {
  "use strict";
  const esc = (s) => String(s == null ? "" : s).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));

  function palette(app) {
    const modal = document.getElementById("palette"), box = document.getElementById("palette-input"), list = document.getElementById("palette-list");
    let items = [], cursor = 0;
    const commands = () => [
      { label: "Validate lineup", key: "Ctrl+Enter", run: () => app.validate() },
      { label: "Save lineup", key: "Ctrl+S", run: () => app.save() },
      { label: "Apply lineup (make it active)", key: "", run: () => app.apply() },
      { label: "New lineup…", key: "Ctrl+N", run: () => app.newLineup() },
      { label: "New lineup from the current one…", key: "", run: () => app.newLineup(app.current && app.current.name) },
      { label: "New agent bio…", key: "", run: () => app.newBio() },
      { label: "Auto-layout", key: "A", run: () => app.canvas.autoLayout() },
      { label: "Fit to screen", key: "F", run: () => app.canvas.fit() },
      { label: "Zoom 100%", key: "", run: () => app.canvas.zoomTo(1) },
      { label: "Toggle run view", key: "", run: () => app.toggleRun() },
      { label: "Toggle light / dark", key: "", run: () => app.toggleTheme() },
      { label: "Toggle the left rail", key: "[", run: () => document.body.classList.toggle("rail-hidden") },
      { label: "Toggle the inspector", key: "]", run: () => document.body.classList.toggle("inspector-hidden") },
      { label: "Show the tour", key: "?", run: () => tour(app, true) },
      { label: "Open docs: lineups and bios (docs/AGENTS.md)", key: "", run: () => window.open("https://github.com/roloVibes/Halo-Harness/blob/master/docs/AGENTS.md", "_blank") },
      { label: "Open docs: Studio (docs/STUDIO.md)", key: "", run: () => window.open("https://github.com/roloVibes/Halo-Harness/blob/master/docs/STUDIO.md", "_blank") },
      ...(app.lineups || []).map((l) => ({ label: `Switch to lineup: ${l.name}`, key: "", run: () => app.selectLineup(l.name) })),
      ...(app.bios || []).map((b) => ({ label: `Edit agent bio: ${b.name}`, key: "", run: () => { app.bioName = b.name; app.showTab("agent"); } })),
    ];
    const score = (q, s) => { q = q.toLowerCase(); s = s.toLowerCase(); if (!q) return 1; let i = 0, hit = 0; for (const c of q) { const j = s.indexOf(c, i); if (j < 0) return 0; hit += j === i ? 2 : 1; i = j + 1; } return hit + (s.startsWith(q) ? 10 : 0); };
    const draw = () => {
      const q = box.value.trim();
      items = commands().map((c) => [score(q, c.label), c]).filter(([s]) => s > 0).sort((a, b) => b[0] - a[0]).slice(0, 14).map(([, c]) => c);
      cursor = Math.min(cursor, Math.max(0, items.length - 1));
      list.innerHTML = items.map((c, i) => `<li class="${i === cursor ? "on" : ""}" data-i="${i}">${esc(c.label)}${c.key ? `<span class="kbd">${esc(c.key)}</span>` : ""}</li>`).join("") || `<li><span class="hint">nothing matches</span></li>`;
    };
    const open = () => { modal.classList.add("open"); box.value = ""; cursor = 0; draw(); setTimeout(() => box.focus(), 0); };
    const close = () => modal.classList.remove("open");
    const run = (i) => { const c = items[i]; close(); if (c) c.run(); };
    box.addEventListener("input", () => { cursor = 0; draw(); });
    box.addEventListener("keydown", (ev) => {
      if (ev.key === "ArrowDown") { cursor = Math.min(items.length - 1, cursor + 1); draw(); ev.preventDefault(); }
      else if (ev.key === "ArrowUp") { cursor = Math.max(0, cursor - 1); draw(); ev.preventDefault(); }
      else if (ev.key === "Enter") run(cursor);
      else if (ev.key === "Escape") close();
    });
    list.addEventListener("click", (ev) => { const li = ev.target.closest("li[data-i]"); if (li) run(Number(li.dataset.i)); });
    modal.addEventListener("click", (ev) => { if (ev.target === modal) close(); });
    return { open, close, toggle: () => (modal.classList.contains("open") ? close() : open()) };
  }

  const STEPS = [
    ["Your lineup, as a graph", "Every card is an assignment: an agent bio (what it IS) in a role (the slot it fills), with the model that resolves for it. Edges are delegation from main, org reporting lines and pipeline order."],
    ["Drag, drop, connect", "Drag an agent from the left rail onto the canvas to add an assignment. Drag cards to arrange them; positions are remembered per lineup. Shift-drag selects several."],
    ["The inspector", "Select a card to edit the assignment, then the Agent tab to edit the bio behind it: models, tools, limits, acceptance. The YAML tab shows the file as it will be written, and edits go both ways."],
    ["Validate, save, apply", "Validate runs the same checks the CLI does. Save writes YAML to your user scope (or the project). Apply makes this the active lineup for new sessions, exactly like halo teams use."],
  ];
  function tour(app, force = false) {
    let seen = false; try { seen = localStorage.getItem("halo-studio-tour") === "done"; } catch (e) {}
    if (seen && !force) return;
    const modal = document.getElementById("tour"); let i = 0;
    const draw = () => {
      document.getElementById("tour-title").textContent = STEPS[i][0];
      document.getElementById("tour-text").textContent = STEPS[i][1];
      document.getElementById("tour-steps").innerHTML = STEPS.map((_, k) => `<i class="${k === i ? "on" : ""}"></i>`).join("");
      document.getElementById("tour-next").textContent = i === STEPS.length - 1 ? "Done" : "Next";
    };
    const finish = () => { modal.classList.remove("open"); try { localStorage.setItem("halo-studio-tour", "done"); } catch (e) {} };
    document.getElementById("tour-next").onclick = () => { if (i < STEPS.length - 1) { i += 1; draw(); } else finish(); };
    document.getElementById("tour-skip").onclick = finish;
    modal.classList.add("open"); draw();
  }

  window.studioPalette = palette; window.studioTour = tour;
})();
