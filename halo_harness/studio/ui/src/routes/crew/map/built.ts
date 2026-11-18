// What a session just built (3.6.0.2 R29 R30 R31 R32), from the `builder_done` frame (P2b, R25: `{id, outcome, wrote,
// undo, next, this_session, maps, t}`), kept per session for the page's life while the session is open (dropped when
// its row ends: `keepOpen`). Bound by litStore's startLit. Only an `applied` outcome counts; it never opens a drawer,
// changes the section or pops up (R32): it sets the view-bar word, the pair's Just built, the head and the tags.
// - the word "new" (R29) until the drawer is opened (`seenBuilt`);
// - the kind of head (R31): a map other than the one the session runs on ("other": the pair Running | Just built, R30),
//   a change to the running map ("running": the same drawing, tagged), a workflow on no map ("workflow");
// - Just built is chosen once per session, at the frame's arrival, only while the pointer is not on the drawing, no
//   card is open and the pair was never pressed (`holding`, set by the drawing); otherwise only its tab is marked;
// - tags "new {t}" (R29) on the boxes the build wrote: every box of a map it made, the boxes new or changed in a map it
//   edited (against the body drawn before), the boxes running a workflow it wrote (their block rows too).
import { createStore, useStore } from "../../../lib/store";
import { current, putBody, bump } from "./mapFiles";
import type { DrawBox, MapFile } from "./mapTypes";
import { isAuto } from "./truthWords";

export type BuiltKind = "workflow" | "running" | "other";
export type Built = { t: number; kind: BuiltKind | null; map: string; workflow: string; next: string };
type S = { last: Record<string, Built>; word: Record<string, boolean>; which: Record<string, "running" | "built">;
  marked: Record<string, boolean>; pressed: Record<string, boolean>; auto: Record<string, boolean>;
  tags: Record<string, Record<string, number>>; flows: Record<string, Record<string, number>> };

export const built = createStore<S>({ last: {}, word: {}, which: {}, marked: {}, pressed: {}, auto: {}, tags: {}, flows: {} });
export const useBuilt = <T,>(f: (s: S) => T): T => useStore(built, f);

const holds = new Map<string, boolean>();
/** The drawing of `sid` is under the pointer or has a card open (hold.ts), as R30 asks at a frame's arrival. */
export const holding = (sid: string, on: boolean): void => void (on ? holds.set(sid, true) : holds.delete(sid));

type Wrote = { kind?: string; name?: string; added?: boolean; removed?: boolean };

/** One `builder_done` frame of session `sid`. */
export function takeBuilt(sid: string, d: Record<string, unknown>, now = Date.now() / 1000): void {
  if (!sid || d.outcome !== "applied") return;
  const t = Number(d.t) || now;
  const wrote = (Array.isArray(d.wrote) ? d.wrote : []).filter((w): w is Wrote => !!w && typeof w === "object" && !(w as Wrote).removed);
  const maps = wrote.filter((w) => w.kind === "map" && w.name).map((w) => ({ name: String(w.name), added: !!w.added }));
  const flows = wrote.filter((w) => w.kind === "workflow" && w.name).map((w) => String(w.name));
  const running = !d.this_session || isAuto(String(d.this_session)) ? "auto" : String(d.this_session);
  const bodies = d.maps && typeof d.maps === "object" ? (d.maps as Record<string, MapFile>) : {};
  const v = String(d.undo || `b${t}`);
  const tags: Record<string, number> = {};
  for (const m of maps) {
    const before = current(m.name), body = bodies[m.name];
    if (m.added) tags[`${m.name}:*`] = t;
    else if (body && before) {
      for (const b of body.boxes || []) {
        const old = before.boxes.find((x) => x.id === b.id);
        if (!old || JSON.stringify(old) !== JSON.stringify(b)) tags[`${m.name}:${b.id}`] = t;
      }
    }
    if (body && typeof body === "object") putBody(m.name, v, body, flows);
    else bump(m.name, v); // R28: a body over 64 KB: read once, after the draw that needs it
  }
  const other = maps.find((m) => m.name !== running);
  const onRunning = maps.some((m) => m.name === running) || flows.some((w) => (current(running)?.boxes || []).some((b) => b.workflow === w));
  const kind: BuiltKind | null = other ? "other" : onRunning ? "running" : flows.length ? "workflow" : null;
  built.update((s) => {
    const choose = kind === "other" && !s.auto[sid] && !s.pressed[sid] && !holds.get(sid);
    return {
      last: { ...s.last, [sid]: { t, kind, map: other?.name || (kind === "running" ? running : ""), workflow: flows[0] || "", next: String(d.next || "") } },
      word: { ...s.word, [sid]: true },
      which: choose ? { ...s.which, [sid]: "built" } : s.which,
      auto: choose ? { ...s.auto, [sid]: true } : s.auto,
      marked: { ...s.marked, [sid]: kind === "other" && !choose ? true : !!s.marked[sid] && kind !== "other" },
      tags: { ...s.tags, [sid]: { ...s.tags[sid], ...tags } },
      flows: { ...s.flows, [sid]: { ...s.flows[sid], ...Object.fromEntries(flows.map((w) => [w, t])) } },
    };
  });
}

/** R29: the drawer was opened: the word goes. */
export const seenBuilt = (sid: string): void => built.update((s) => (s.word[sid] ? { word: { ...s.word, [sid]: false } } : {}));

/** R30: the pair pressed. */
export const pressPair = (sid: string, which: "running" | "built"): void =>
  built.update((s) => ({ which: { ...s.which, [sid]: which }, pressed: { ...s.pressed, [sid]: true },
    marked: which === "built" ? { ...s.marked, [sid]: false } : s.marked }));

/** R29: the tag time of box `b` on map `map` in session `sid`, else null (main is never tagged). */
export function tagOf(s: Pick<S, "tags" | "flows">, sid: string, map: string, b: DrawBox): number | null {
  if (b.main) return null;
  const tg = s.tags[sid] || {}, fl = s.flows[sid] || {};
  return tg[`${map}:${b.id}`] || tg[`${map}:*`] || (b.block ? fl[b.block.workflow] : 0) || null;
}

/** R29: "for the page's life while the session is open": a session gone from the rows forgets what it built. */
export function keepOpen(open: string[]): void {
  const keep = new Set(open);
  const st = built.get();
  if (Object.keys(st.last).every((sid) => keep.has(sid)) && Object.keys(st.tags).every((sid) => keep.has(sid))) return;
  const only = <T,>(r: Record<string, T>) => Object.fromEntries(Object.entries(r).filter(([k]) => keep.has(k)));
  built.update((s) => ({ last: only(s.last), word: only(s.word), which: only(s.which), marked: only(s.marked), pressed: only(s.pressed),
    auto: only(s.auto), tags: only(s.tags), flows: only(s.flows) }));
}
