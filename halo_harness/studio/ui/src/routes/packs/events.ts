// A pack's event lines (3.2.0.0 R3): a `pack_event` frame of a kind the pack
// declares under `contributes.studio.events` renders with the pack's label
// and its `line` template, `{field}` (or `{a.b}`) read from the frame's data;
// a kind no running pack declares keeps the generic line: the pack, the kind
// and the data in short. Session's Live column (shared/liveFeed.ts), Fleet's
// Activity (fleet/pload.ts) and the pack's events panels all read lineOf.
import { short } from "../orchestra/format";
import { packs } from "./store";

const FIELD = /\{([A-Za-z0-9_.-]+)\}/g;

/** The template with each `{field}` filled from `data` ("?" for a field the frame does not carry). */
export function fill(template: string, data: unknown): string {
  return template.replace(FIELD, (_m, key: string) => {
    let cur: unknown = data;
    for (const part of key.split(".")) cur = cur && typeof cur === "object" ? (cur as Record<string, unknown>)[part] : undefined;
    if (cur === undefined || cur === null) return "?";
    return typeof cur === "object" ? short(JSON.stringify(cur), 80) : String(cur);
  });
}

export type PackLine = { label: string; text: string; known: boolean };

export function lineOf(pack: string, kind: string, data: unknown): PackLine {
  const ev = packs.get().reg.packs.find((p) => p.id === pack)?.events[kind];
  if (ev && ev.line) return { label: ev.label || kind, text: fill(ev.line, data), known: true };
  const tail = data === null || data === undefined ? "" : " " + short(typeof data === "string" ? data : JSON.stringify(data), 120);
  return { label: "PACK", text: `${pack} ${kind}${tail}`, known: false };
}

/** A feed frame's pack, kind and data (null when it is not a pack_event). */
export function packOf(data: unknown): { pack: string; kind: string; data: unknown } | null {
  const d = (data || {}) as { pack?: unknown; kind?: unknown; data?: unknown };
  return typeof d.pack === "string" && typeof d.kind === "string" ? { pack: d.pack, kind: d.kind, data: d.data ?? null } : null;
}
