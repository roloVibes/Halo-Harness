// The map as the page draws it (3.6.0.0 R3): the saved file, plus the builder's preview for this map drawn where it
// would land -- ghost boxes and dashed lines with their When (the design: "ghost boxes and dashed lines on the map"); a
// line it would take out is drawn dashed too. Boxes nothing hands work to wait under the map ("Not connected yet");
// one the builder or this page just made is tagged `new`.
import type { Change } from "../types";
import { boxKind, boxName, type DrawBox, type DrawLine, type MapBoxFile, type MapFile, type MapLine } from "./mapTypes";

export type MapView = { boxes: DrawBox[]; strip: DrawBox[]; lines: DrawLine[] };

function asBox(b: MapBoxFile, ghost: boolean, made: string[]): DrawBox {
  const names = b.workflow ? [b.workflow] : Array.isArray(b.agent) ? b.agent : [b.agent || b.id];
  return { id: b.id, kind: boxKind(b), name: Array.isArray(b.agent) ? `main decides: ${names.join(", ")}` : boxName(b), names,
           ghost: ghost || undefined, isNew: ghost || made.includes(b.id) || undefined };
}

/** The ghost rows of the builder's preview that touch the map `name` (only the ticked ones draw). */
export function ghostRows(pending: Change[], name: string): Change[] {
  return pending.filter((c) => c.target === `map:${name}` && c.ticked && c.ghost);
}

export function view(file: MapFile | null, pending: Change[], made: string[]): MapView {
  if (!file) return { boxes: [], strip: [], lines: [] };
  let boxes: { b: MapBoxFile; ghost: boolean }[] = file.boxes.map((b) => ({ b, ghost: false }));
  let lines: DrawLine[] = file.lines.map((l) => ({ ...l }));
  for (const c of ghostRows(pending, file.name)) {
    const g = c.ghost!;
    if (g.op === "map_box_add" && g.box && !boxes.some((x) => x.b.id === g.box!.id)) boxes.push({ b: g.box as MapBoxFile, ghost: true });
    if (g.op === "map_line_add" && g.line) lines.push({ ...(g.line as MapLine), ghost: true });
    if (g.op === "map_line_set") lines = lines.map((l) => (l.from === g.from && l.to === g.to ? { ...l, when: g.when as MapLine["when"], ghost: true } : l));
    if (g.op === "map_line_remove") lines = lines.map((l) => (l.from === g.from && l.to === g.to ? { ...l, ghost: true } : l));
    if (g.op === "map_box_remove") boxes = boxes.map((x) => (x.b.id === g.id ? { ...x, ghost: true } : x));
  }
  const fed = new Set(lines.map((l) => l.to));
  const all = boxes.map((x) => asBox(x.b, x.ghost, made));
  const main: DrawBox = { id: "main", kind: "agent", name: file.main?.agent || "main", names: [file.main?.agent || "main"], main: true };
  return { boxes: [main, ...all.filter((b) => fed.has(b.id))], strip: all.filter((b) => !fed.has(b.id)), lines };
}

/** Every box a line from `from` may go to (the connect dot's list): not itself, not main, not one that would make a circle. */
export function targets(v: MapView, from: string): DrawBox[] {
  const next = new Map<string, string[]>();
  for (const l of v.lines) next.set(l.from, [...(next.get(l.from) || []), l.to]);
  const reaches = (a: string, b: string, seen = new Set<string>()): boolean =>
    a === b || (!seen.has(a) && (seen.add(a), (next.get(a) || []).some((n) => reaches(n, b, seen))));
  return [...v.boxes, ...v.strip].filter((b) => !b.main && b.id !== from && !b.ghost && !reaches(b.id, from)
                                         && !v.lines.some((l) => l.from === from && l.to === b.id));
}

/** One sentence when a line would make a circle (the route refuses it too). */
export function circleLine(v: MapView, from: string, to: string): string {
  const next = new Map<string, string[]>();
  for (const l of v.lines) next.set(l.from, [...(next.get(l.from) || []), l.to]);
  const walk = (a: string, seen: Set<string>): boolean => a === from || (!seen.has(a) && (seen.add(a), (next.get(a) || []).some((n) => walk(n, seen))));
  return walk(to, new Set()) ? `${from} -> ${to} would make a circle: a loop lives inside a workflow as "repeat until".` : "";
}
