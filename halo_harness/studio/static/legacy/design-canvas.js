/* Halo Studio -- the Design canvas (3.0.1.0 round D3): a DOM layer of artboard
   frame cards. Pan with space-drag, middle button or a drag on the empty
   background; zoom with Ctrl+wheel; fit; drag a card by its title row. Each
   card: the frame (a sandboxed iframe for HTML, an img for a render, a link
   card for pdf/mp4), a device select, comment pins, a version slider. */
(function () {
  "use strict";
  const { h, esc } = window.inspector;
  const $ = (id) => document.getElementById(id);
  const d = window.designMode;
  const DEV = { phone: [390, 844], tablet: [820, 1100], desktop: [1280, 800] };
  const SHOW = 520;  // the frame's display width in the world, at most
  const cam = d.cam = { x: 24, y: 24, z: 1 };
  let space = false;

  const posKey = () => "halo-design-pos:" + d.slug;
  const savedPos = () => { try { return JSON.parse(localStorage.getItem(posKey()) || "{}"); } catch (e) { return {}; } };
  const apply = () => {
    const c = $("design-canvas"); if (!c) return;
    $("design-world").style.transform = `translate(${cam.x}px, ${cam.y}px) scale(${cam.z})`;
    c.style.backgroundPosition = `${cam.x}px ${cam.y}px`; c.style.backgroundSize = `${24 * cam.z}px ${24 * cam.z}px`;
    $("d-zoom").textContent = Math.round(cam.z * 100) + "%";
  };
  const zoomAt = (px, py, factor) => {
    const z = Math.max(0.1, Math.min(3, cam.z * factor)); const k = z / cam.z;
    cam.x = px - (px - cam.x) * k; cam.y = py - (py - cam.y) * k; cam.z = z; apply();
  };
  d.setTool = (tool) => {
    d.tool = tool; const c = $("design-canvas"); if (!c) return;
    c.classList.toggle("commenting", tool === "comment");
    document.querySelectorAll("#design-pill [data-tool]").forEach((b) => b.setAttribute("aria-pressed", String(b.dataset.tool === tool)));
  };
  d.fit = () => {
    const cards = [...document.querySelectorAll("#design-world .d-card")]; const c = $("design-canvas");
    if (!cards.length || !c) { cam.x = 24; cam.y = 24; cam.z = 1; apply(); return; }
    const box = cards.reduce((b, k) => ({ x0: Math.min(b.x0, k.offsetLeft), y0: Math.min(b.y0, k.offsetTop), x1: Math.max(b.x1, k.offsetLeft + k.offsetWidth), y1: Math.max(b.y1, k.offsetTop + k.offsetHeight) }), { x0: 1e9, y0: 1e9, x1: -1e9, y1: -1e9 });
    const w = box.x1 - box.x0, hh = box.y1 - box.y0;
    cam.z = Math.max(0.1, Math.min(1.25, (c.clientWidth - 80) / w, (c.clientHeight - 80) / hh));
    cam.x = (c.clientWidth - w * cam.z) / 2 - box.x0 * cam.z; cam.y = (c.clientHeight - hh * cam.z) / 2 - box.y0 * cam.z; apply();
  };
  d.centerOn = (id) => {
    const k = document.querySelector(`#design-world .d-card[data-id="${CSS.escape(id)}"]`), c = $("design-canvas"); if (!k || !c) return;
    cam.x = c.clientWidth / 2 - (k.offsetLeft + k.offsetWidth / 2) * cam.z; cam.y = c.clientHeight / 2 - (k.offsetTop + k.offsetHeight / 2) * cam.z; apply();
  };

  d.mountCanvas = () => {
    if ($("design-canvas")) { apply(); return; }
    const c = h(`<div id="design-canvas" tabindex="0" role="region" aria-label="Design canvas: artboards">
      <div id="design-world"></div><div id="design-empty" style="display:none"></div>
      <div id="design-pill" role="toolbar" aria-label="Canvas tools"><button data-tool="select" aria-pressed="true" title="Select and drag (V)">Select</button><button data-tool="comment" aria-pressed="false" title="Pin a comment on a frame (C)">Comment</button>
        <span class="sep"></span><button id="d-zoom-out" title="Zoom out" aria-label="Zoom out">−</button><button id="d-zoom" title="Reset to 100%">100%</button><button id="d-zoom-in" title="Zoom in" aria-label="Zoom in">+</button><button id="d-fit" title="Fit (F)">fit</button></div></div>`);
    $("canvas-wrap").appendChild(c);
    c.querySelectorAll("[data-tool]").forEach((b) => b.addEventListener("click", () => d.setTool(b.dataset.tool)));
    $("d-zoom-out").onclick = () => zoomAt(c.clientWidth / 2, c.clientHeight / 2, 1 / 1.2); $("d-zoom-in").onclick = () => zoomAt(c.clientWidth / 2, c.clientHeight / 2, 1.2);
    $("d-zoom").onclick = () => { cam.z = 1; apply(); }; $("d-fit").onclick = d.fit;
    c.addEventListener("wheel", (ev) => {
      ev.preventDefault(); const r = c.getBoundingClientRect();
      if (ev.ctrlKey || ev.metaKey) zoomAt(ev.clientX - r.left, ev.clientY - r.top, Math.exp(-ev.deltaY * 0.0015)); else { cam.x -= ev.deltaX; cam.y -= ev.deltaY; apply(); }
    }, { passive: false });
    c.addEventListener("pointerdown", (ev) => {
      const bg = ev.target === c || ev.target === $("design-world") || ev.target === $("design-empty");
      if (!(ev.button === 1 || (ev.button === 0 && (space || bg)))) return;
      ev.preventDefault(); c.setPointerCapture(ev.pointerId); c.classList.add("panning");
      const s = { x: ev.clientX, y: ev.clientY, cx: cam.x, cy: cam.y };
      const move = (m) => { cam.x = s.cx + m.clientX - s.x; cam.y = s.cy + m.clientY - s.y; apply(); };
      const up = () => { c.classList.remove("panning"); c.removeEventListener("pointermove", move); c.removeEventListener("pointerup", up); };
      c.addEventListener("pointermove", move); c.addEventListener("pointerup", up);
    });
    document.addEventListener("keydown", (ev) => { if (ev.code === "Space" && d.active() && !/^(INPUT|TEXTAREA|SELECT|BUTTON)$/.test(document.activeElement.tagName)) { space = true; c.classList.add("space"); ev.preventDefault(); } });
    document.addEventListener("keyup", (ev) => { if (ev.code === "Space") { space = false; c.classList.remove("space"); } });
    window.addEventListener("message", onEditMessage);
    apply();
  };

  // -- cards ------------------------------------------------------------------------------
  const frameSrc = (a, n, file, edit) => `/design-files/${encodeURIComponent(d.slug)}/${encodeURIComponent(a.id)}/${n ? "v" + n + "/" : ""}${encodeURIComponent(file)}?t=${d.bust[a.id] || 0}${edit ? "&edit=1" : ""}`;
  const flow = () => {
    const saved = savedPos(); let x = 40, y = 40, rowH = 0;
    document.querySelectorAll("#design-world .d-card").forEach((k) => {
      const p = saved[k.dataset.id];
      if (p) { k.style.left = p.x + "px"; k.style.top = p.y + "px"; }
      else { if (x > 40 && x + k.offsetWidth > 1700) { x = 40; y += rowH + 48; rowH = 0; } k.style.left = x + "px"; k.style.top = y + "px"; }
      if (!p) { x += k.offsetWidth + 48; rowH = Math.max(rowH, k.offsetHeight); }
    });
  };
  function frameHtml(a, ver, edit) {
    const file = a.render, n = ver === a.latest ? 0 : ver;
    if (!file) return `<div class="d-nofile">no preview yet</div>`;
    const src = frameSrc(a, n, file, edit);
    if (file === "index.html") return `<div class="d-scaler"><iframe sandbox="allow-scripts" title="${esc(a.title || a.id)} prototype" src="${esc(src)}"></iframe></div>`;
    if (/\.(png|svg)$/.test(file)) return `<img src="${esc(src)}" alt="${esc(a.title || a.id)} render">`;
    return `<a class="d-linkcard" target="_blank" rel="noopener" href="${esc(src)}"><b>${esc(file)}</b><span>open the ${esc(file.split(".").pop())} in a new tab</span></a>`;
  }
  function cardEl(a) {
    let k = document.querySelector(`#design-world .d-card[data-id="${CSS.escape(a.id)}"]`);
    if (k) return k;
    k = h(`<article class="d-card" data-id="${esc(a.id)}" tabindex="-1"><header class="d-title"></header><div class="d-frame"><div class="d-body"></div><div class="d-overlay"></div></div><footer class="d-foot"></footer></article>`);
    $("design-world").appendChild(k);
    k.querySelector(".d-title").addEventListener("pointerdown", (ev) => {
      if (ev.target.closest("select,button") || ev.button !== 0) return;
      ev.preventDefault(); const t = ev.currentTarget; t.setPointerCapture(ev.pointerId); k.classList.add("dragging");
      const s = { x: ev.clientX, y: ev.clientY, l: k.offsetLeft, t: k.offsetTop };
      const move = (m) => { k.style.left = s.l + (m.clientX - s.x) / cam.z + "px"; k.style.top = s.t + (m.clientY - s.y) / cam.z + "px"; };
      const up = () => { k.classList.remove("dragging"); t.removeEventListener("pointermove", move); t.removeEventListener("pointerup", up);
        const all = savedPos(); all[a.id] = { x: k.offsetLeft, y: k.offsetTop }; try { localStorage.setItem(posKey(), JSON.stringify(all)); } catch (e) {} };
      t.addEventListener("pointermove", move); t.addEventListener("pointerup", up);
      d.selected = a.id; d.rail(); if (d.tab === "knobs" || d.tab === "export") d.showTab(d.tab);
    });
    k.querySelector(".d-overlay").addEventListener("click", (ev) => { if (d.tool === "comment" && !ev.target.closest(".d-pin,.d-pop")) pinHere(k, ev); });
    return k;
  }
  function pinHere(k, ev) {
    const o = k.querySelector(".d-overlay"), r = o.getBoundingClientRect();
    const x = Math.round(((ev.clientX - r.left) / r.width) * 1000) / 10, y = Math.round(((ev.clientY - r.top) / r.height) * 1000) / 10;
    o.querySelectorAll(".d-pop").forEach((p) => p.remove());
    const pop = h(`<form class="d-pop" style="left:${x}%;top:${y}%"><textarea rows="3" placeholder="What should change here?" aria-label="Comment text"></textarea><div><button class="btn primary">Pin comment</button><button type="button" class="btn ghost">Cancel</button></div></form>`);
    const send = async () => {
      const text = pop.querySelector("textarea").value.trim(); if (!text) return;
      try { await d.call("POST", "comment", { artboard: k.dataset.id, text, x, y, path: "" }); pop.remove(); await d.reload(true); } catch (e) { d.toast(e.message, "bad"); }
    };
    pop.addEventListener("submit", (e) => { e.preventDefault(); send(); }); pop.querySelector(".ghost").onclick = () => pop.remove();
    pop.querySelector("textarea").addEventListener("keydown", (e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); send(); } else if (e.key === "Escape") pop.remove(); });
    o.appendChild(pop); pop.querySelector("textarea").focus();
  }
  function drawCard(a, i) {
    const k = cardEl(a); const vs = (a.versions || []).slice().reverse(); const idx = Math.min(d.view[a.id] == null ? vs.length - 1 : d.view[a.id], vs.length - 1);
    const ver = vs.length ? vs[Math.max(idx, 0)] : 0; const isHtml = a.render === "index.html"; const dev = d.device[a.id] || "desktop"; const edit = !!d.editing[a.id] && ver === a.latest;
    k.classList.toggle("selected", a.id === d.selected); k.setAttribute("aria-label", `Artboard ${a.title || a.id}: ${a.kind}${a.app ? ", " + a.app : ""}, version ${ver}`);
    const t = k.querySelector(".d-title");
    t.innerHTML = `<b>${esc(a.title || a.id)}</b><span class="d-meta">${esc(a.kind)}</span>${a.app ? `<span class="badge live">${esc(a.app)}</span>` : ""}<span class="d-ver">v${ver || "–"}</span><span class="spacer"></span>`
      + (isHtml ? `<select class="d-device" aria-label="Device frame">${Object.keys(DEV).map((x) => `<option value="${x}"${x === dev ? " selected" : ""}>${x} ${DEV[x][0]}</option>`).join("")}</select><button class="btn ghost d-edit" aria-pressed="${edit}" title="Edit the text in place; Ctrl+S saves">${edit ? "Done editing" : "Edit text"}</button>` : "");
    const dv = t.querySelector(".d-device"); if (dv) dv.onchange = () => { d.device[a.id] = dv.value; drawCard(a, i); flow(); };
    const eb = t.querySelector(".d-edit"); if (eb) eb.onclick = () => { d.editing[a.id] = !d.editing[a.id]; if (d.editing[a.id]) d.view[a.id] = undefined; drawCard(a, i); };
    const body = k.querySelector(".d-body"), fr = k.querySelector(".d-frame"); const key = `${d.slug}|${a.render}|${ver === a.latest ? "current" : ver}|${edit}|${d.bust[a.id] || 0}`;  // a direct edit saves a new version without reloading its frame
    if (body.dataset.key !== key) { body.dataset.key = key; body.innerHTML = frameHtml(a, ver || a.latest, edit); }
    if (isHtml) { const [W, H] = DEV[dev], s = Math.min(1, SHOW / W); fr.style.width = W * s + "px"; fr.style.height = H * s + "px"; const sc = body.querySelector(".d-scaler"); if (sc) { sc.style.cssText = `width:${W}px;height:${H}px;transform:scale(${s})`; } }
    else { fr.style.width = SHOW + "px"; fr.style.height = ""; const im = body.querySelector("img"); if (im) im.onload = flow; }
    const o = k.querySelector(".d-overlay"); o.querySelectorAll(".d-pin").forEach((p) => p.remove());
    d.openComments().filter((c) => c.artboard === a.id).forEach((c, n) => o.appendChild(h(`<button class="d-pin${c.source === "critique" ? " crit" : ""}" style="left:${esc(Number(c.x) || 0)}%;top:${esc(Number(c.y) || 0)}%" aria-label="Comment ${n + 1} on ${esc(a.id)}: ${esc(c.text)}" title="${esc(c.text)}" data-id="${esc(c.id)}">${n + 1}</button>`)));
    o.querySelectorAll(".d-pin").forEach((p) => p.addEventListener("click", () => { d.showTab("comments"); }));
    const f = k.querySelector(".d-foot");
    f.innerHTML = vs.length > 1 ? `<input type="range" class="d-slider" min="0" max="${vs.length - 1}" value="${Math.max(idx, 0)}" aria-label="Version of ${esc(a.id)}"><span class="d-vlabel">${ver === a.latest ? `v${ver} (current)` : `v${ver} of ${a.latest}`}</span>${ver !== a.latest ? '<button class="btn ghost d-restore">Restore this version</button>' : ""}` : `<span class="d-vlabel">${vs.length ? "v" + vs[0] + " (current)" : "no versions yet"}</span>`;
    const sl = f.querySelector(".d-slider"); if (sl) sl.oninput = () => { d.view[a.id] = Number(sl.value); if (d.editing[a.id]) d.editing[a.id] = false; drawCard(a, i); };
    const rb = f.querySelector(".d-restore"); if (rb) rb.onclick = async () => { try { await d.call("POST", `artboard/${encodeURIComponent(a.id)}/restore`, { version: ver }); d.view[a.id] = undefined; d.bust[a.id] = (d.bust[a.id] || 0) + 1; await d.reload(true); d.toast(`${a.id}: v${ver} restored as the newest version`, "ok"); } catch (e) { d.toast(e.message, "bad"); } };
  }
  d.drawCards = () => {
    const world = $("design-world"); if (!world) return;
    const boards = (d.data && d.data.artboards) || [];
    world.querySelectorAll(".d-card").forEach((k) => { if (!boards.some((a) => a.id === k.dataset.id)) k.remove(); });
    const first = !world.querySelector(".d-card");
    boards.forEach((a, i) => drawCard(a, i)); flow();
    if (first && boards.length) d.fit();
  };

  async function onEditMessage(ev) {  // a contenteditable frame posts its page on Ctrl+S / blur
    if (!ev.data || ev.data.type !== "halo-design-edit" || typeof ev.data.html !== "string") return;
    const fr = [...document.querySelectorAll("#design-world iframe")].find((f) => f.contentWindow === ev.source); if (!fr) return;
    try { const r = await d.call("POST", "text-edit", { artboard: fr.closest(".d-card").dataset.id, html: ev.data.html }); d.toast(r.versions.length ? `Text saved as v${r.versions[0][1]}` : "No text change", "ok"); await d.reload(false); } catch (e) { d.toast(e.message, "bad"); }
  }
})();
