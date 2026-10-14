// Studio's API client. The per-launch token arrives in the URL fragment
// (`#t=...`); it is kept in sessionStorage under the same key the legacy page
// uses, removed from the address bar, and sent as a bearer header. Errors are
// typed: an ApiError carries the HTTP status and the server's `problems`.

const KEY = "halo-studio-token";
const FRAGMENT = /[#&]t=([A-Za-z0-9_-]+)/;
let current = "";

function adopt(hash: string): boolean {
  const m = FRAGMENT.exec(hash || "");
  if (!m) return false;
  current = m[1];
  try {
    sessionStorage.setItem(KEY, current);
  } catch {
    /* storage off: the token lives in memory for this page */
  }
  history.replaceState(null, "", location.pathname + location.search);
  return true;
}

if (!adopt(location.hash)) {
  try {
    current = sessionStorage.getItem(KEY) || "";
  } catch {
    current = "";
  }
}

const listeners = new Set<() => void>();
window.addEventListener("hashchange", () => {
  // a fresh `halo studio` URL pasted over a stale tab: only the fragment changes
  if (adopt(location.hash)) listeners.forEach((fn) => fn());
});

export function token(): string {
  return current;
}

export function onTokenChange(fn: () => void): () => void {
  listeners.add(fn);
  return () => listeners.delete(fn);
}

export class ApiError extends Error {
  status: number;
  problems: string[];
  data: Record<string, unknown>;
  constructor(status: number, message: string, data: Record<string, unknown> = {}) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.data = data;
    const p = data.problems;
    this.problems = Array.isArray(p) ? p.map(String) : [];
  }
}

export type Query = Record<string, string | number | boolean | undefined | null>;

export async function call<T = unknown>(method: string, path: string, body?: unknown, query?: Query): Promise<T> {
  const url = new URL("api/" + path.replace(/^\/+/, ""), location.origin + "/");
  for (const [k, v] of Object.entries(query || {})) {
    if (v !== undefined && v !== null && v !== "") url.searchParams.set(k, String(v));
  }
  const headers: Record<string, string> = { Authorization: "Bearer " + current, Accept: "application/json" };
  const init: RequestInit = { method, headers };
  if (body !== undefined) {
    headers["Content-Type"] = "application/json";
    init.body = JSON.stringify(body);
  }
  let res: Response;
  try {
    res = await fetch(url, init);
  } catch (e) {
    throw new ApiError(0, "Studio server unreachable: " + (e instanceof Error ? e.message : String(e)));
  }
  const text = await res.text();
  let data: Record<string, unknown> = {};
  if (text) {
    try {
      data = JSON.parse(text);
    } catch {
      data = { error: text.slice(0, 400) };
    }
  }
  if (!res.ok) throw new ApiError(res.status, String(data.error || res.statusText), data);
  return data as T;
}

export const api = {
  get: <T = unknown>(path: string, query?: Query) => call<T>("GET", path, undefined, query),
  post: <T = unknown>(path: string, body?: unknown, query?: Query) => call<T>("POST", path, body ?? {}, query),
  put: <T = unknown>(path: string, body?: unknown, query?: Query) => call<T>("PUT", path, body ?? {}, query),
  del: <T = unknown>(path: string, query?: Query) => call<T>("DELETE", path, undefined, query),
};
