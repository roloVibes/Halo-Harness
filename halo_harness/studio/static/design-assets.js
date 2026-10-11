/* Halo Studio -- Design mode assets (3.0.1.0 round D5): the rail's Assets list
   with a drop zone. Drag files from the desktop onto the rail or the canvas to
   upload them to the project's assets/ folder; the Chat box then gets "Use
   assets/<name> ...". Dropping an image on a frame card appends "Place
   assets/<name> on <artboard>" instead. Click an asset to insert its path. */
(function () {
  "use strict";
  const { h, esc } = window.inspector;
  const $ = (id) => document.getElementById(id);
  const d = window.designMode;
  d.assets = [];
  const kb = (n) => (n < 1024 ? n + " B" : n < 1048576 ? Math.round(n / 1024) + " KB" : (n / 1048576).toFixed(1) + " MB");

  const toBase64 = (file) => new Promise((resolve, reject) => {
    const r = new FileReader();
    r.onload = () => resolve(String(r.result).split(",", 2)[1] || "");
    r.onerror = () => reject(new Error("could not read " + file.name));
    r.readAsDataURL(file);
  });
  const addToPrompt = (text) => {
    d.draft = (d.draft ? d.draft.replace(/\s+$/, "") + "\n" : "") + text;
    const p = document.querySelector(".d-prompt"); if (p) { p.value = d.draft; p.focus(); }
  };
  d.loadAssets = async () => {
    if (!d.slug) { d.assets = []; return; }
    try { d.assets = (await d.call("GET", "assets")).assets; } catch (e) { d.assets = []; }
    if (d.active()) d.paintAssets();
  };
  d.paintAssets = (root) => {
    root = root || $("design-rail"); if (!root) return;
    let box = $("d-assets");
    if (!box) { box = h(`<div id="d-assets"></div>`); root.appendChild(box); }
    box.innerHTML = `<h3>Assets <button class="btn ghost" id="d-asset-add" title="Add files (U)"${d.slug ? "" : " disabled"}>+ add</button></h3>
      <div class="d-drop" id="d-drop">${d.slug ? "Drop images or files here" : "Open a project to add assets"}</div>
      <ul class="d-assetlist">${d.assets.map((a) => `<li data-path="${esc(a.path)}" title="Insert ${esc(a.path)} into the prompt">${a.thumb ? `<img src="${esc(a.thumb)}" alt="">` : `<i class="d-kind">${esc(a.kind)}</i>`}<span class="name">${esc(a.name)}</span><small>${kb(a.size)}</small></li>`).join("")}</ul>`;
    $("d-asset-add").onclick = d.pickAssets; $("d-drop").onclick = d.pickAssets;
    box.querySelector(".d-assetlist").onclick = (ev) => { const li = ev.target.closest("li[data-path]"); if (li) { addToPrompt(li.dataset.path); d.toast(`${li.dataset.path} added to the prompt`, "ok"); } };
    if (!d.assetsLoaded || d.assetsLoaded !== d.slug) { d.assetsLoaded = d.slug; d.loadAssets(); }
  };
  d.uploadAssets = async (files, board) => {
    if (!d.slug) { d.toast("Open a project first", "warn"); return; }
    for (const f of files) {
      try {
        const row = await d.call("POST", "assets", { name: f.name, data_base64: await toBase64(f) });
        addToPrompt(board && row.kind === "image" ? `Place ${row.path} on ${board}` : `Use ${row.path} `);
        d.toast(`${row.path} uploaded`, "ok");
      } catch (e) { d.toast(e.message, "bad"); }
    }
    d.loadAssets();
  };
  d.pickAssets = () => {
    if (!d.slug) { d.toast("Open a project first", "warn"); return; }
    const inp = h(`<input type="file" multiple style="display:none">`); document.body.appendChild(inp);
    inp.onchange = () => { d.uploadAssets([...inp.files]); inp.remove(); }; inp.click();
  };

  const files = (ev) => (ev.dataTransfer && [...ev.dataTransfer.types].includes("Files") ? [...ev.dataTransfer.files] : null);
  const wire = (el) => {
    el.addEventListener("dragover", (ev) => { if (d.active() && files(ev)) { ev.preventDefault(); el.classList.add("dropping"); } });
    el.addEventListener("dragleave", () => el.classList.remove("dropping"));
    el.addEventListener("drop", (ev) => {
      el.classList.remove("dropping"); const fs = d.active() && files(ev); if (!fs) return;
      ev.preventDefault(); const card = ev.target.closest && ev.target.closest(".d-card");
      d.uploadAssets(fs, card ? card.dataset.id : "");
    });
  };
  wire($("rail"));
  const mount = d.mountCanvas; d.mountCanvas = () => { mount(); const c = $("design-canvas"); if (c && !c.dataset.drop) { c.dataset.drop = "1"; wire(c); } };
})();
