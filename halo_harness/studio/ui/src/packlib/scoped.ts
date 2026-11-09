// api.lib's requests (3.3.13.0 R2, extension API 1.2; 3.3.14.0 R1, the review's #4 and #5: a client scoped to the
// pack, what `api.lib` always meant to be). A pack's page gets `scopedApi(pack, key)`: `api.get/post/put/del`, `call`,
// `fetchJson(path, init?)` and `authUrl(path)`, with Studio's token and never the shell's owner proof, reaching
//   - any method on its own routes, `packs/<id>/...`;
//   - GET on its own `pack/<id>/file|data|config|mode|artifact/...`, POST on its own `pack/<id>/publish|attention`;
//   - PUT on its own canvas layouts, `layout/<id>:<name>`;
//   - GET on the read-only routes a page draws from (READ_ONLY);
// anything else throws an Error naming that rule, and no request is made. `authUrl(path)` is for what sends no header
// (an iframe, an image, a video, a link): the pack's own routes or files with its key in `?k=` (a GET-only key Studio
// derives for this pack), never the launch token. The shell's own client (lib/api.ts) stays the shell's.
import { ApiError, apiUrl, plainCall, type Query } from "../lib/api";

/** The core routes any pack's page may GET (the read-only data a page draws from). */
export const READ_ONLY = [/^pack\/registry$/, /^state$/, /^session$/, /^tools$/, /^models(\/|$)/, /^layout\/[^/]+$/,
  /^media\/(status|models|workflows)(\/|$)/, /^glossary(\/|$)/, /^field-help(\/|$)/];

export type ScopedApi = {
  api: {
    get: <T = unknown>(path: string, query?: Query) => Promise<T>;
    post: <T = unknown>(path: string, body?: unknown, query?: Query) => Promise<T>;
    put: <T = unknown>(path: string, body?: unknown, query?: Query) => Promise<T>;
    del: <T = unknown>(path: string, query?: Query) => Promise<T>;
  };
  call: <T = unknown>(method: string, path: string, body?: unknown, query?: Query) => Promise<T>;
  fetchJson: <T = unknown>(path: string, init?: { method?: string; body?: unknown; query?: Query }) => Promise<T>;
  authUrl: (path: string) => string;
  ApiError: typeof ApiError;
};

/** The path the browser will ask for, after /api/ and decoded (`..` resolved as the URL parser does), or null. */
function routeOf(url: URL): string | null {
  let path: string;
  try {
    path = decodeURIComponent(url.pathname);
  } catch {
    return null;
  }
  if (url.origin !== location.origin || !path.startsWith("/api/") || /(^|\/)\.\.?(\/|$)/.test(path.slice(5))) return null;
  return path.slice(5);
}

/** Whether a pack's page may send `method` to `route` (the path after /api/, decoded). */
export function allowed(pack: string, method: string, route: string): boolean {
  if (!pack) return method === "GET" && READ_ONLY.some((re) => re.test(route));
  if (route.startsWith(`packs/${pack}/`)) return true;
  if (method === "GET" && new RegExp(`^pack/${pack}/(file|data|config|mode|artifact)(/|$)`).test(route)) return true;
  if (method === "POST" && new RegExp(`^pack/${pack}/(publish|attention)$`).test(route)) return true;
  if (method === "PUT" && route.startsWith(`layout/${pack}:`) && !route.slice(7).includes("/")) return true;
  return method === "GET" && READ_ONLY.some((re) => re.test(route));
}

function rule(pack: string, method: string, path: string): Error {
  const own = pack ? `its own routes (packs/${pack}/...), its own pack/${pack}/ files and calls, ` : "";
  return new Error(`${method} ${path}: a pack's page reaches ${own}and the read-only routes a page draws from ` +
    "(api.lib's client; docs/EXTENSION_API.md \"api.lib\"); the rest is Studio's own page");
}

/** The client `api.lib` hands pack `pack` (`key`: its key from the registry, for `authUrl`). */
export function scopedApi(pack: string, key: string): ScopedApi {
  const call = <T = unknown>(method: string, path: string, body?: unknown, query?: Query): Promise<T> => {
    const route = routeOf(apiUrl(path, query));
    const verb = method.toUpperCase();
    if (route === null || !allowed(pack, verb, route)) return Promise.reject(rule(pack, verb, path));
    return plainCall<T>(verb, path, body, query);
  };
  const authUrl = (path: string): string => {
    const p = "/api/" + path.replace(/^\/+/, "").replace(/^api\//, "");
    const route = routeOf(new URL(p, location.origin + "/"));
    const own = !!pack && !!key && route !== null &&
      (route.startsWith(`packs/${pack}/`) || route.startsWith(`pack/${pack}/file/`));
    if (!own) throw rule(pack, "GET", path);
    return p + (p.includes("?") ? "&" : "?") + "k=" + encodeURIComponent(key);
  };
  return {
    api: {
      get: (path, query) => call("GET", path, undefined, query),
      post: (path, body, query) => call("POST", path, body ?? {}, query),
      put: (path, body, query) => call("PUT", path, body ?? {}, query),
      del: (path, query) => call("DELETE", path, undefined, query),
    },
    call,
    fetchJson: (path, init) => call(init?.method || (init?.body !== undefined ? "POST" : "GET"), path, init?.body, init?.query),
    authUrl,
    ApiError,
  };
}
