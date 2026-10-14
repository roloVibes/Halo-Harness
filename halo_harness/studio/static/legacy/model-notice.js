/* Halo Studio -- the model picker's catalog notice (3.0.4.0).
   Under every model dropdown: how many models the catalog holds and a
   Refresh link; when it holds none, WHY (per provider) and a Refresh button
   that pulls the catalogs and redraws every picker on the page. */
(function () {
  "use strict";
  const esc = (s) => String(s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const h = (html) => { const t = document.createElement("template"); t.innerHTML = html.trim(); return t.content.firstElementChild; };
  let busy = false;

  async function refreshAll(button) {
    if (busy) return;
    busy = true;
    const label = button.textContent;
    button.disabled = true; button.textContent = "Refreshing...";
    try {
      const r = await window.api.modelsRefresh();
      window.app.models = await window.api.models().catch(() => []);
      document.dispatchEvent(new CustomEvent("halo-models", { detail: r }));
      if (window.app.status) window.app.status(r.rows ? `${r.rows} models in the catalog` : (r.reason || "no models found"));
    } catch (e) {
      if (window.app.status) window.app.status("model refresh failed: " + (e && e.message || e));
    } finally { busy = false; button.disabled = false; button.textContent = label; }
  }

  /* Draws the notice into `slot` for the current catalog and returns nothing;
     `redraw` is the picker's own draw() so a refresh re-lists its options. */
  function modelNotice(slot, redraw) {
    const rows = window.app.models || [];
    slot.innerHTML = "";
    slot.className = "model-notice" + (rows.length ? " ok" : " empty");
    if (rows.length) {
      const line = h(`<div class="hint">${rows.length} models in the catalog · <a href="#" data-act="refresh">refresh</a></div>`);
      line.querySelector("a").addEventListener("click", (ev) => { ev.preventDefault(); refreshAll(ev.target); });
      slot.appendChild(line);
    } else {
      const box = h(`<div class="notice" data-testid="models-empty"><b>No models in the catalog yet.</b><div class="why mono">reading providers...</div><div class="row"><button class="btn" type="button">Refresh models</button><span class="hint">or pick "Type a ref..." above</span></div></div>`);
      box.querySelector("button").addEventListener("click", (ev) => refreshAll(ev.target));
      slot.appendChild(box);
      window.api.modelsStatus().then((st) => {
        const why = box.querySelector(".why");
        const lines = [st.reason || ""].concat((st.providers || []).filter((p) => p.enabled || p.credentials).map((p) => `${p.label}: ${p.status}${typeof p.model_count === "number" ? ` · ${p.model_count} cached` : ""}`));
        why.innerHTML = lines.filter(Boolean).map((l) => `<div>${esc(l)}</div>`).join("");
      }).catch(() => {});
    }
    const once = () => { document.removeEventListener("halo-models", once); if (!slot.isConnected) return; redraw(); modelNotice(slot, redraw); };
    document.addEventListener("halo-models", once);
  }

  window.modelNotice = modelNotice;
})();
