// Studio's API client. The per-launch token arrives in the URL fragment
// (`#t=...`); it is kept in sessionStorage (`halo-studio-token`), removed
// from the address bar, and sent as a bearer header. Errors are
// typed: an ApiError carries the HTTP status and the server's `problems`.
// 3.3.14.0 R1 (#4): the shell's own `call` also sends `X-Halo-Owner` (lib/owner.ts), with the `fetch` this module
// took at boot; `plainCall` is the same request without it (a pack's scoped client, packlib/scoped.ts). 3.4.1.2
// (PACKS-2): the request's init and headers are objects with no prototype, so no getter a script put on
// Object.prototype is asked for a field while fetch reads them.
import { DROPPED, limitFor, overLimit, within } from "./apiLimit";
import { makeOwnerProof, ownerProof } from "./owner";
import { isOwnerRefusal, ownerRefused } from "./ownerTab";

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

/** 3.6.0.0 R10: the page says "Studio has stopped" and stops asking only when Studio HAS stopped: it said goodbye
 *  on the live feed as it closed (a `studio_stopped` frame, `markStopped()`), or nothing has answered on this port at
 *  all for STOP_AFTER_MS (it was ended hard). A shorter silence is a blip -- an SSH forward re-made, a Studio paused --
 *  and the page keeps reconnecting by itself (the glance's own promise). Once stopped every later request fails at
 *  once and the live feed stays down (lib/events.ts reads `stopped()`); the page's own button starts over. */
const STOP_AFTER_MS = 120_000;
let unreachableSince = 0;
let gone = false;

export function stopped(): boolean {
  return gone;
}

function showStopped(): void {
  if (document.getElementById("halo-studio-stopped")) return;
  const box = document.createElement("div");
  box.id = "halo-studio-stopped";
  box.setAttribute("role", "alertdialog");
  box.setAttribute("data-testid", "studio-stopped");
  box.style.cssText = "position:fixed;inset:0;z-index:2147483000;display:flex;align-items:center;justify-content:center;" +
    "background:rgba(4,8,14,0.82);color:var(--text,#e6edf3);font:15px/1.5 system-ui,sans-serif;padding:16px";
  const card = document.createElement("div");
  card.style.cssText = "max-width:460px;background:var(--panel,#0d1520);border:1px solid var(--line,#2a3a4a);" +
    "border-radius:10px;padding:20px 22px";
  const h = document.createElement("h2");
  h.textContent = "Studio has stopped";
  h.style.cssText = "margin:0 0 8px;font-size:18px";
  const p = document.createElement("p");
  p.textContent = "The Halo that started this Studio has closed, and Studio closed with it. This page has stopped asking. " +
    "Start it again with `halo studio` (or `halo`), then open the address it prints.";
  p.style.margin = "0 0 14px";
  const again = document.createElement("button");
  again.textContent = "Try this address again";
  again.setAttribute("data-testid", "studio-stopped-retry");
  again.onclick = () => location.reload();
  card.append(h, p, again);
  box.append(card);
  document.body.append(box);
}

/** Studio said it is closing (or has been unreachable for STOP_AFTER_MS): say so and stop asking. */
export function markStopped(): void {
  if (gone) return;
  gone = true;
  try {
    showStopped();
  } catch {
    /* no document (a test): the flag alone stops the asking */
  }
  stoppedListeners.forEach((fn) => fn());
}

function noteReached(ok: boolean): void {
  if (ok) {
    unreachableSince = 0;
    return;
  }
  const now = Date.now();
  if (!unreachableSince) unreachableSince = now;
  if (now - unreachableSince >= STOP_AFTER_MS) markStopped();
}

const stoppedListeners = new Set<() => void>();

/** The live feed lost its connection: one plain request says whether a server still answers on this port. */
export function probeServer(): void {
  if (gone) return;
  fetchOwn(location.origin + "/", { method: "GET", cache: "no-store" }).then(
    () => noteReached(true),
    () => noteReached(false),
  );
}

export function onStopped(fn: () => void): () => void {
  stoppedListeners.add(fn);
  return () => stoppedListeners.delete(fn);
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

async function request<T>(owner: boolean, method: string, path: string, body?: unknown, query?: Query, signal?: AbortSignal): Promise<T> {
  const url = apiUrl(path, query);
  if (revoked) throw new ApiError(401, "this page's key is no longer Studio's: open the page again from Studio");
  if (gone) throw new ApiError(0, "Studio has stopped");
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
  const ms = limitFor(path); // P4 batch 9: a read that never ends fails at its limit like any failed read (apiLimit.ts)
  let res: Response, text: string;
  try {
    [res, text] = await within(async (own) => {
      init.signal = own;
      const r = await fetchOwn(url, init);
      return [r, await r.text()] as const;
    }, ms, signal);
  } catch (e) {
    if (e === DROPPED) throw new ApiError(0, DROPPED.message); // O1-6: its caller dropped it: quiet, Studio not marked unreached
    const slow = e instanceof Error && e.message === overLimit(ms).message;
    if (!slow) noteReached(false); // one slow answer is not a stopped server
    throw new ApiError(0, "Studio server unreachable: " + (e instanceof Error ? e.message : String(e)));
  }
  noteReached(true);
  let data: Record<string, unknown> = {};
  if (text) {
    try {
      data = JSON.parse(text);
    } catch {
      data = { error: text.slice(0, 400) };
    }
  }
  if (!res.ok) {
    // 3.6.0.6 P: a write refused for want of the proof raises the one toast with Make this tab yours (lib/ui/Toast.tsx)
    if (owner && res.status === 403 && isOwnerRefusal(String(data.error || ""))) ownerRefused();
    throw new ApiError(res.status, String(data.error || res.statusText), data);
  }
  return data as T;
}

/** The shell's own request: the token and the owner proof. */
export function call<T = unknown>(method: string, path: string, body?: unknown, query?: Query, signal?: AbortSignal): Promise<T> {
  return request<T>(true, method, path, body, query, signal);
}

/** The same request with the token alone (what a pack's scoped client sends). */
export function plainCall<T = unknown>(method: string, path: string, body?: unknown, query?: Query): Promise<T> {
  return request<T>(false, method, path, body, query);
}

export const api = {
  get: <T = unknown>(path: string, query?: Query, signal?: AbortSignal) => call<T>("GET", path, undefined, query, signal),
  post: <T = unknown>(path: string, body?: unknown, query?: Query) => call<T>("POST", path, body ?? {}, query),
  put: <T = unknown>(path: string, body?: unknown, query?: Query) => call<T>("PUT", path, body ?? {}, query),
  del: <T = unknown>(path: string, query?: Query) => call<T>("DELETE", path, undefined, query),
};
