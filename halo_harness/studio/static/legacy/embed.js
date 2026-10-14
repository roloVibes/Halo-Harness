/* Halo Studio -- the classic page framed inside the shell (3.0.4.0 R6b).
   With ?embedded=1 (the shell's legacySrc sets it) there is ONE header, the
   shell's: the logo and the Roles / Org / Design buttons go, what is left of
   <header id="top"> becomes a slim toolbar (the lineup, company or project,
   the scope, the actions; embed.css), the status line goes to the shell's
   status bar ({type: "legacy-status", mode, text} by postMessage) instead of
   this page's footer, the theme follows the shell's (halo.studio.theme), and
   R / O / D (and Alt+1..5) switch the shell's section rather than this
   frame. Opened on its own (/legacy/), nothing here runs: the full header
   stays. */
(function () {
  "use strict";
  if (!/[?&]embedded=1\b/.test(location.search)) return;
  const $ = (id) => document.getElementById(id);
  const root = document.documentElement;
  const own = (location.search.match(/[?&]mode=(roles|org|design)\b/) || [])[1] || "roles";
  const SECTIONS = ["orchestra", "roles", "org", "design", "flow"];
  const post = (msg) => { try { if (window.parent !== window) window.parent.postMessage(msg, location.origin); } catch (e) {} };
  root.dataset.embedded = "1";

  // -- one header: the toolbar ----------------------------------------------------------
  const top = $("top");
  top.dataset.testid = "legacy-toolbar";
  top.setAttribute("aria-label", "Toolbar");
  top.querySelectorAll(".brand, .mode-toggle").forEach((n) => n.remove());
  const label = document.createElement("span");
  label.className = "embed-label mono";
  label.textContent = { roles: "LINEUP", org: "COMPANY", design: "PROJECT" }[own];
  const project = document.createElement("span");
  project.className = "embed-project";
  top.prepend(label, project);

  // -- the status line goes to the shell --------------------------------------------------
  const ids = ["status-valid", "status-active", "status-session", "status-dirty"];
  let last = "";
  const send = () => {
    const text = ids.map((id) => ($(id) ? $(id).textContent.trim() : "")).filter((t) => t && t !== "—").join(" · ");
    if (own === "design") {
      const d = window.designMode && window.designMode.data;
      project.textContent = d && d.meta ? d.meta.name : "none open: pick one on the left";
    }
    if (text !== last) { last = text; post({ type: "legacy-status", mode: own, text }); }
  };
  new MutationObserver(send).observe($("status"), { childList: true, characterData: true, subtree: true });
  send();

  // -- the theme follows the shell ---------------------------------------------------------
  const theme = () => {
    let t = "dark"; try { t = localStorage.getItem("halo.studio.theme") || "dark"; } catch (e) {}
    const light = t === "light" || (t === "auto" && window.matchMedia("(prefers-color-scheme: light)").matches);
    root.dataset.theme = light ? "light" : "dark";
  };
  theme();
  window.addEventListener("storage", (ev) => { if (ev.key === "halo.studio.theme") theme(); });
  window.matchMedia("(prefers-color-scheme: light)").addEventListener("change", theme);

  // -- the section keys belong to the shell ------------------------------------------------
  window.addEventListener("keydown", (ev) => {
    if (/^(INPUT|TEXTAREA|SELECT)$/.test((document.activeElement || {}).tagName || "")) return;
    let to = "";
    if (ev.altKey && !ev.ctrlKey && !ev.metaKey && !ev.shiftKey && /^Digit[1-5]$/.test(ev.code)) to = SECTIONS[Number(ev.code.slice(5)) - 1];
    else if (!ev.altKey && !ev.ctrlKey && !ev.metaKey && ["r", "o", "d"].includes(ev.key)) to = { r: "roles", o: "org", d: "design" }[ev.key];
    if (!to) return;
    ev.preventDefault(); ev.stopImmediatePropagation();
    if (to !== own) post({ type: "legacy-section", to });
  }, true);
})();
