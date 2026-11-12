// Studio's API client. The per-launch token arrives in the URL fragment
// (`#t=...`); it is kept in sessionStorage (`halo-studio-token`), removed
// from the address bar, and sent as a bearer header. Errors are
// typed: an ApiError carries the HTTP status and the server's `problems`.
// 3.3.14.0 R1 (#4): the shell's own `call` also sends `X-Halo-Owner` (lib/owner.ts), with the `fetch` this module
// took at boot; `plainCall` is the same request without it (a pack's scoped client, packlib/scoped.ts). 3.4.1.2
// (PACKS-2): the request's init and headers are objects with no prototype, so no getter a script put on
// Object.prototype is asked for a field while fetch reads them.
import { makeOwnerProof, ownerProof } from "./owner";

const fetchOwn = window.fetch.bind(window);
const bare = Object.create.bind(Object, null) as () => Record<string, unknown>;
const KEY = "halo-studio-token";
const FRAGMENT = /[#&]t=([A-Za-z0-9_-]+)/;
let current = "";
let revoked = false; // revoke() below; a fresh address pasted over the tab (a new #t=) is a key again

function adopt(hash: string): boolean {
  const m = FRAGMENT.exec(hash || "");
  if (!m) return false;
  current = m[1];
  revoked = false;
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
makeOwnerProof(current); // made now, before any pack module loads (routes/packs/importPack.ts waits for it)

const listeners = new Set<() => void>();
window.addEventListener("hashchange", () => {
  // a fresh `halo studio` URL pasted over a stale tab: only the fragment changes
  if (adopt(location.hash)) listeners.forEach((fn) => fn());
});

export function token(): string {
  return current;
}

/** 3.4.1.1 (63): this page's key is no longer Studio's (a restarted Studio makes a new one, never the old): every
 *  later request fails at once without asking, and the feed, with no token, stays down instead of retrying. */
export function revoke(): void {
  revoked = true;
  current = "";
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

/** `/api/<path>` with the query's set values, as a URL (the scoped client checks the path the browser will ask for). */
export function apiUrl(path: string, query?: Query): URL {
  const url = new URL("api/" + path.replace(/^\/+/, ""), location.origin + "/");
  for (const [k, v] of Object.entries(query || {})) {
    if (v !== undefined && v !== null && v !== "") url.searchParams.set(k, String(v));
  }
  return url;
}

async function request<T>(owner: boolean, method: string, path: string, body?: unknown, query?: Query): Promise<T> {
  const url = apiUrl(path, query);
  if (revoked) throw new ApiError(401, "this page's key is no longer Studio's: open the page again from Studio");
  const headers = bare() as Record<string, string>;
  headers.Authorization = "Bearer " + current;
  headers.Accept = "application/json";
  const proof = owner ? ownerProof(current) : "";
  if (proof) headers["X-Halo-Owner"] = proof;
  const init = bare() as RequestInit;
  init.method = method;
  init.headers = headers;
  if (body !== undefined) {
    headers["Content-Type"] = "application/json";
    init.body = JSON.stringify(body);
  }
  let res: Response;
  try {
    res = await fetchOwn(url, init);
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

/** The shell's own request: the token and the owner proof. */
export function call<T = unknown>(method: string, path: string, body?: unknown, query?: Query): Promise<T> {
  return request<T>(true, method, path, body, query);
}

/** The same request with the token alone (what a pack's scoped client sends). */
export function plainCall<T = unknown>(method: string, path: string, body?: unknown, query?: Query): Promise<T> {
  return request<T>(false, method, path, body, query);
}

export const api = {
  get: <T = unknown>(path: string, query?: Query) => call<T>("GET", path, undefined, query),
  post: <T = unknown>(path: string, body?: unknown, query?: Query) => call<T>("POST", path, body ?? {}, query),
  put: <T = unknown>(path: string, body?: unknown, query?: Query) => call<T>("PUT", path, body ?? {}, query),
  del: <T = unknown>(path: string, query?: Query) => call<T>("DELETE", path, undefined, query),
};
