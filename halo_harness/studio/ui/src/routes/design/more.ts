// The rest of what the Design panels do (3.0.7.0 R3b, the classic page's
// last features): turn a knob (POST control: a css: knob is applied at once
// and saved as a version, any other waits for the next turn), pin a comment
// where you clicked (POST comment) and resolve one (POST comments/resolve),
// sync the design system from a folder or a URL (POST sync, then a result
// dialog) and save edited tokens (PUT system), and "3 directions": the Send
// path with `variants: 3` (the server writes the directions prompt), the new
// artboards then laid out in one row under the others.
import { ApiError } from "../../lib/api";
import { toast } from "../../lib/store";
import { send } from "./actions";
import { design, live, openDialog } from "./store";
import { call, movePositions, reload } from "./sync";
import { rowUnder } from "./layout";
import type { SystemSheet } from "./types";

const msg = (e: unknown) => (e instanceof ApiError ? e.problems[0] || e.message : String(e));
const timers = new Map<string, number>();

/** A knob moved: posted 150 ms after the last change (a slider sends many). */
export function setKnob(aid: string, name: string, value: unknown): void {
  const key = aid + "\u0000" + name;
  window.clearTimeout(timers.get(key));
  timers.set(key, window.setTimeout(() => void postKnob(aid, name, value), 150));
}

async function postKnob(aid: string, name: string, value: unknown): Promise<void> {
  try {
    const r = await call<{ queued?: boolean; value?: string; versions?: [string, number][] }>("POST", "control", { artboard: aid, name, value });
    const made = (r.versions || []).find(([a]) => a === aid);
    const note = r.queued ? "next turn" : made ? `v${made[1]}` : "no change";
    design.update((s) => ({ knobNote: { ...s.knobNote, [aid]: note }, bust: made ? { ...s.bust, [aid]: (s.bust[aid] || 0) + 1 } : s.bust }));
    if (r.queued) toast(`${name} is saved: the next turn applies it`, "info");
    await reload();
  } catch (e) {
    toast(msg(e), "error", 5000);
  }
}

/** Pin the comment being written (store `pinAt`) with `text`. */
export async function pinComment(text: string): Promise<void> {
  const at = design.get().pinAt;
  if (!at || !text.trim()) return;
  design.update(() => ({ busy: "comment" }));
  try {
    await call("POST", "comment", { artboard: at.aid, text: text.trim(), x: at.x, y: at.y, path: "" });
    design.update(() => ({ pinAt: null }));
    toast(`Comment pinned on ${at.aid}: Send comments turns the open pins into one turn`, "done");
    await reload();
  } catch (e) {
    toast(msg(e), "error", 5000);
  } finally {
    design.update(() => ({ busy: "" }));
  }
}

export async function resolveComment(id: string): Promise<void> {
  try {
    await call("POST", "comments/resolve", { ids: [id] });
    design.update(() => ({ pinOpen: "" }));
    toast("Comment resolved", "done");
    await reload();
  } catch (e) {
    toast(msg(e), "error", 5000);
  }
}

export async function syncSystem(source: string): Promise<boolean> {
  const src = source.trim();
  if (!src) return (toast("Sync reads a folder path or a URL: type one first", "info"), false);
  design.update(() => ({ busy: "sync" }));
  try {
    const r = await call<{ system: SystemSheet; tokens: number }>("POST", "sync", { source: src });
    const groups = Object.entries(r.system.tokens || {}).map(([g, v]) => [g, Object.keys(v).length] as [string, number]);
    openDialog({ kind: "synced", source: src, tokens: r.tokens, groups, sources: r.system.sources || [] });
    await reload();
    return true;
  } catch (e) {
    toast(msg(e), "error", 6000);
    return false;
  } finally {
    design.update(() => ({ busy: "" }));
  }
}

/** Save the token sheet with `edits` ("group\u0000name" -> value) applied. */
export async function saveTokens(edits: Record<string, string>): Promise<boolean> {
  const sys = design.get().data?.system || {};
  const tokens: Record<string, Record<string, string>> = {};
  for (const [g, vals] of Object.entries(sys.tokens || {})) tokens[g] = { ...vals };
  for (const [key, v] of Object.entries(edits)) {
    const [g, n] = key.split("\u0000");
    if (tokens[g] && n in tokens[g]) tokens[g][n] = v;
  }
  try {
    await call("PUT", "system", { system: { ...sys, tokens } });
    toast("Design system saved: the next turn uses it", "done");
    await reload();
    return true;
  } catch (e) {
    toast(msg(e), "error", 5000);
    return false;
  }
}

/** An artboard id prefix: lower-case letters, digits and hyphens. */
export const baseOf = (v: string) => v.trim().toLowerCase().replace(/[^a-z0-9-]+/g, "-").replace(/^-+|-+$/g, "").slice(0, 24) || "direction";

/** Three directions of the message box's text, named <base>-a, -b, -c. */
export async function directions(base = "", n = 3): Promise<void> {
  const s = design.get();
  if (!s.draft.trim()) {
    design.update((x) => ({ focusSend: x.focusSend + 1 }));
    return toast("Write what to design in the message box, then ask for 3 directions", "info");
  }
  if (live(s)) return toast("A turn already runs in this project: wait for it, or Cancel turn", "info");
  const before = (s.data?.artboards || []).map((a) => a.id);
  await send(s.draft, { variants: n, base: baseOf(base || s.sel || "direction") }, `${n} directions`);
  const tid = design.get().turn?.id;
  if (!tid) return;
  const watch = design.subscribe(() => {
    const t = design.get().turn;
    if (t && t.id === tid) return; // still running, or done and the project not read again yet
    watch();
    const now = design.get();
    const fresh = (now.data?.artboards || []).map((a) => a.id).filter((id) => !before.includes(id));
    if (!fresh.length) return;
    movePositions(rowUnder(now.data?.artboards || [], now.positions, now.device, fresh));
    design.update(() => ({ sel: fresh[0] }));
    toast(`${fresh.length} direction(s) side by side: ${fresh.join(", ")}`, "done", 4500);
  });
}
