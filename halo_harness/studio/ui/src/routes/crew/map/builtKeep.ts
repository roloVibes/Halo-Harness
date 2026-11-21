// 3.6.0.9 V batch 2 (the owner's point 34: "it's not showing any changes"): what Session shows after a build -- the
// head, the ready lines and the "new" tags (built.ts `last`, `tags`, `flows`) and the lines of a workflow changed by a
// plain write (`changed`) -- kept per session id in this tab's sessionStorage, so a reload of the page says it again.
// Nothing leaves the machine; no server change. Every read and write is wrapped: a storage that refuses or is full
// changes nothing (the page works as it did before). At most the KEEP_MAX newest sessions; the oldest entry leaves.
// Pure: no React, no store (built.ts reads it once at the page's start and writes through it on each change).
import type { Built } from "./built";

export const KEEP_KEY = "halo.studio.built";
export const KEEP_MAX = 20;

type Times = Record<string, Record<string, number>>;
/** The part of built.ts's state that is kept. */
export type Kept = { last: Record<string, Built>; tags: Times; flows: Times; changed: Times };

const times = (r: unknown): Record<string, number> =>
  r && typeof r === "object" ? Object.fromEntries(Object.entries(r).filter(([, v]) => typeof v === "number" && Number.isFinite(v))) : {};

/** What this tab kept (empty when nothing is, or the storage cannot be read). */
export function readKept(): Kept {
  const out: Kept = { last: {}, tags: {}, flows: {}, changed: {} };
  try {
    const raw: unknown = JSON.parse(sessionStorage.getItem(KEEP_KEY) || "{}");
    if (!raw || typeof raw !== "object") return out;
    for (const [sid, e] of Object.entries(raw as Record<string, Record<string, unknown>>)) {
      if (!e || typeof e !== "object") continue;
      const last = e.last as Built | undefined;
      if (last && typeof last === "object" && typeof last.t === "number") out.last[sid] = last;
      for (const k of ["tags", "flows", "changed"] as const) {
        const t = times(e[k]);
        if (Object.keys(t).length) out[k][sid] = t;
      }
    }
  } catch {
    /* refused or unreadable: nothing kept */
  }
  return out;
}

let wrote: string | null = null;

/** Keep `s` (the newest KEEP_MAX sessions by their latest time); a write that would change nothing is not made. */
export function writeKept(s: Kept): void {
  const sids = new Set([...Object.keys(s.last), ...Object.keys(s.tags), ...Object.keys(s.flows), ...Object.keys(s.changed)]);
  const newest = (sid: string): number =>
    Math.max(s.last[sid]?.t || 0, ...[s.tags, s.flows, s.changed].flatMap((r) => Object.values(r[sid] || {})));
  const keep = [...sids].sort((a, b) => newest(b) - newest(a)).slice(0, KEEP_MAX);
  const text = JSON.stringify(Object.fromEntries(keep.map((sid) => [sid, { last: s.last[sid], tags: s.tags[sid], flows: s.flows[sid], changed: s.changed[sid] }])));
  if (text === wrote) return;
  try {
    if (keep.length) sessionStorage.setItem(KEEP_KEY, text);
    else sessionStorage.removeItem(KEEP_KEY);
    wrote = text;
  } catch {
    /* a storage that refuses or is full: nothing kept, nothing else changes */
  }
}
