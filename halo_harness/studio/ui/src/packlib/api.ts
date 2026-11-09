// api.lib's requests (3.3.13.0 R2, extension API 1.2): Studio's own JSON client with the launch token (`api.get`,
// `call`, ApiError), `fetchJson(path, init?)` for a path under /api/ (a pack's routes: `packs/<id>/<prefix>/...`),
// and `authUrl(path)`: the same address with the token in `?t=`, for what sends no header (an iframe, an image, a
// download link) -- Studio takes it there only on a GET of a pack's routes or module.
import { api, ApiError, call, token, type Query } from "../lib/api";

export { api, ApiError, call, type Query };

/** A JSON request under /api/ with Studio's token; rejects with an ApiError carrying the server's line. */
export function fetchJson<T = unknown>(path: string, init?: { method?: string; body?: unknown; query?: Query }): Promise<T> {
  return call<T>(init?.method || (init?.body !== undefined ? "POST" : "GET"), path, init?.body, init?.query);
}

/** `/api/<path>` with the token in `?t=` (kept beside the path's own query). */
export function authUrl(path: string): string {
  const p = "/api/" + path.replace(/^\/+/, "").replace(/^api\//, "");
  return p + (p.includes("?") ? "&" : "?") + "t=" + encodeURIComponent(token());
}
