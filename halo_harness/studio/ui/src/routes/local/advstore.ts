// 3.3.7.0 R4: the roster adviser's slice (Adviser.tsx; GET local/advise, studio/local_advise_api.py). Each suggestion's
// one button goes to the route that already does that one thing: add -> POST local/library/verify (download, then the
// battery), retire -> POST local/host/<host>/retire (the shelf's retire), point -> POST roles/<role>/point (the role
// write); 3.3.8.0 R4: place -> POST local/place (halo local place --apply). Nothing runs until a button is pressed;
// `said` keeps each suggestion's answer by its id.
import { api, ApiError } from "../../lib/api";
import { createStore, useStore } from "../../lib/store";

export type Cost = { download_gb: number; vram_gb: number | null; window: number | null; beside: string | null; minutes: number };
export type Action = { verb: "add" | "retire" | "point" | "place" | "none"; what: string; model?: string; host?: string; role?: string | null; cli: string };
export type Suggestion = { id: string; rank: number; kind: "gap" | "overlap" | "mismatch" | "freshness" | "placement"; says: string;
  unlocks?: string; frees?: string; cost: Cost; value: number; value_per_gb: number; host: string; action: Action; line: string };
// 3.3.8.0 R4: `placement` -- each lane's score on every candidate across the fleet and the pool, its loading tax
export type Advice = { suggestions: Suggestion[]; head: string; kinds: Record<string, number>; due: boolean; due_why: string;
  placement?: { lines: string[] } };
type Said = { ok: boolean; text: string };
type Adv = { advice: Advice | null; error: string; busy: string; said: Record<string, Said> };

export const adv = createStore<Adv>({ advice: null, error: "", busy: "", said: {} });

export function useAdv<T>(pick: (s: Adv) => T): T {
  return useStore(adv, pick);
}

export async function loadAdvice(host?: string): Promise<void> {
  try {
    const r = await api.get<Advice>("local/advise", host ? { host } : undefined);
    adv.update(() => ({ advice: r, error: "" }));
  } catch (e) {
    adv.update(() => ({ error: e instanceof ApiError ? e.message : String(e) }));
  }
}

function said(id: string, ok: boolean, text: string): void {
  adv.update((s) => ({ busy: "", said: { ...s.said, [id]: { ok, text } } }));
}

/** The one thing a suggestion's button names: nothing else runs. */
export async function act(s: Suggestion): Promise<void> {
  const a = s.action;
  adv.update(() => ({ busy: s.id }));
  try {
    if (a.verb === "add") {
      const name = String(a.model || "");
      await api.post("local/library/verify", { host: a.host || s.host, name, ...(a.role ? { role: a.role } : {}) });
      said(s.id, true, `downloading ${name} onto ${a.host || s.host}, then the battery (the Jobs list shows both)`);
    } else if (a.verb === "retire") {
      const r = await api.post<{ say: string }>(`local/host/${encodeURIComponent(a.host || s.host)}/retire`, { name: a.model, why: s.says.slice(0, 120) });
      said(s.id, true, r.say || `retired ${a.model}`);
    } else if (a.verb === "place") {  // 3.3.8.0 R4: halo local place --apply (host_for on each moved lane, Halo-side)
      const r = await api.post<{ written: string[] }>("local/place", {});
      said(s.id, true, (r.written || []).join(" · ") || "nothing to write");
    } else if (a.verb === "point") {
      const r = await api.post<{ line: string }>(`roles/${encodeURIComponent(String(a.role || ""))}/point`, { to: a.model });
      said(s.id, true, r.line);
    }
  } catch (e) {
    said(s.id, false, e instanceof ApiError ? e.message : String(e));
  }
}
