/* Halo Studio -- the API client. One per-launch token: the server puts it in
   the URL fragment (#t=...) when it opens the browser; the page keeps it in
   sessionStorage and sends it as a bearer header on every call. */
(function () {
  "use strict";
  const KEY = "halo-studio-token";
  let token = "";
  const m = /[#&]t=([A-Za-z0-9_-]+)/.exec(location.hash || "");
  if (m) { token = m[1]; try { sessionStorage.setItem(KEY, token); } catch (e) {} history.replaceState(null, "", location.pathname + location.search); }
  else { try { token = sessionStorage.getItem(KEY) || ""; } catch (e) {} }
  window.addEventListener("hashchange", () => {  // a fresh `halo studio` URL pasted over a stale tab (fragment-only change, no reload)
    const n = /[#&]t=([A-Za-z0-9_-]+)/.exec(location.hash || "");
    if (n) { token = n[1]; try { sessionStorage.setItem(KEY, token); } catch (e) {} history.replaceState(null, "", location.pathname + location.search); location.reload(); }
  });

  async function call(method, path, body, query) {
    const url = new URL("/api/" + path, location.origin);
    if (query) for (const [k, v] of Object.entries(query)) if (v !== undefined && v !== null && v !== "") url.searchParams.set(k, v);
    const init = { method, headers: { "Authorization": "Bearer " + token, "Accept": "application/json" } };
    if (body !== undefined) { init.headers["Content-Type"] = "application/json"; init.body = JSON.stringify(body); }
    let res;
    try { res = await fetch(url, init); } catch (e) { throw new ApiError(0, "Studio server unreachable: " + e.message, {}); }
    let data = {};
    const text = await res.text();
    if (text) { try { data = JSON.parse(text); } catch (e) { data = { error: text.slice(0, 400) }; } }
    if (!res.ok) throw new ApiError(res.status, data.error || res.statusText, data);
    return data;
  }
  class ApiError extends Error { constructor(status, message, data) { super(message); this.status = status; this.data = data || {}; } }

  window.api = {
    ApiError,
    state: () => call("GET", "state"),
    lineups: () => call("GET", "lineups"),
    lineup: (name) => call("GET", "lineup/" + encodeURIComponent(name)),
    saveLineup: (name, raw, scope, duplicate) => call("PUT", "lineup/" + encodeURIComponent(name), { raw }, { scope, duplicate: duplicate ? "1" : "" }),
    saveLineupYaml: (name, yaml, scope) => call("PUT", "lineup/" + encodeURIComponent(name), { yaml }, { scope }),
    applyLineup: (name) => call("POST", "lineup/" + encodeURIComponent(name) + "/apply"),
    newLineup: (name, from, scope) => call("POST", "lineup", { name, from }, { scope }),
    deleteLineup: (name, scope) => call("DELETE", "lineup/" + encodeURIComponent(name), undefined, { scope }),
    layout: (name) => call("GET", "layout/" + encodeURIComponent(name)),
    saveLayout: (name, positions) => call("PUT", "layout/" + encodeURIComponent(name), { positions }),
    bios: () => call("GET", "bios"),
    bio: (name) => call("GET", "bio/" + encodeURIComponent(name)),
    saveBio: (name, raw, scope, duplicate) => call("PUT", "bio/" + encodeURIComponent(name), { raw }, { scope, duplicate: duplicate ? "1" : "" }),
    saveBioYaml: (name, yaml, scope) => call("PUT", "bio/" + encodeURIComponent(name), { yaml }, { scope }),
    newBio: (name, from, scope) => call("POST", "bio", { name, from }, { scope }),
    deleteBio: (name, scope) => call("DELETE", "bio/" + encodeURIComponent(name), undefined, { scope }),
    models: () => call("GET", "models"),
    validate: (kind, raw, name) => call("POST", "validate", { kind, raw, name }),
    toYaml: (raw) => call("POST", "yaml", { raw }),
    fromYaml: (yaml) => call("POST", "yaml", { yaml }),
    session: () => call("GET", "session"),
    tools: () => call("GET", "tools"),
  };
})();
