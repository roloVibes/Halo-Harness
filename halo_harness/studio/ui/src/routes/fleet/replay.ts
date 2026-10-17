// Canvas replay (D12): a finished session played back on the Roles canvas.
// The Roles Live tab's history rows ("replay"), the Fleet agent panel's
// history and the palette call openReplay; it reads `GET fleet/replay` (the
// session's agents and their state changes in time order) and puts it in the
// Roles store (3.0.7.0 R2: the React canvas, no framed page): the scrub bar
// along the bottom of the canvas (routes/roles/Replay.tsx) plays it -- play /
// pause, the speed, the scrub, the clock and the cost so far -- and the cards
// light up the way Live Roles lights them, in the order the agents worked.
// While it plays the live agents wait underneath; closing the bar (x or Esc)
// goes back to what runs now.
import { api, ApiError } from "../../lib/api";
import { goSection, toast } from "../../lib/store";
import { roles } from "../roles/store";
import type { Replay, ReplayEvent, ReplayMeta } from "../roles/types";

type ReplayView = ReplayMeta & { states: ReplayEvent[] };

export const SPEEDS = [1, 10, 60, 240, 960];
const TICK_MS = 100;
let timer = 0;

export async function openReplay(session: string, harness = "local"): Promise<boolean> {
  let view: ReplayView;
  try {
    view = await api.get<ReplayView>("fleet/replay", { session, harness });
  } catch (e) {
    toast(`No replay: ${e instanceof ApiError ? e.message : String(e)}`, "error", 5000);
    return false;
  }
  const events = (view.states || []).filter((e) => e && typeof e.t === "number" && e.agent_id).sort((a, b) => a.t - b.t);
  if (!events.length) {
    toast("That session left no agent history to replay", "info", 4000);
    return false;
  }
  const { states: _states, ...meta } = view;
  const t0 = Math.min(Number(meta.started) || events[0].t, events[0].t);
  const t1 = Math.max(Number(meta.ended) || 0, events[events.length - 1].t, t0 + 1);
  const speed = SPEEDS.find((s) => (t1 - t0) / s <= 40) || SPEEDS[SPEEDS.length - 1];
  roles.update(() => ({ replay: { meta, events, t: t0, t0, t1, speed, playing: false } }));
  goSection("roles");
  play(true);
  return true;
}

function patch(fn: (r: Replay) => Partial<Replay>): void {
  roles.update((s) => (s.replay ? { replay: { ...s.replay, ...fn(s.replay) } } : {}));
}

export function play(on: boolean): void {
  window.clearInterval(timer);
  patch((r) => ({ playing: on, t: on && r.t >= r.t1 ? r.t0 : r.t }));
  if (!on) return;
  timer = window.setInterval(() => {
    const r = roles.get().replay;
    if (!r) return window.clearInterval(timer);
    const t = Math.min(r.t1, r.t + (TICK_MS / 1000) * r.speed);
    patch(() => ({ t, playing: t < r.t1 }));
    if (t >= r.t1) window.clearInterval(timer);
  }, TICK_MS);
}

/** The scrub: a fraction 0..1 of the session; it pauses the playback. */
export function scrub(frac: number): void {
  window.clearInterval(timer);
  patch((r) => ({ playing: false, t: r.t0 + Math.max(0, Math.min(1, frac)) * (r.t1 - r.t0) }));
}

export const setSpeed = (speed: number) => patch(() => ({ speed: speed || 60 }));

export function closeReplay(): void {
  window.clearInterval(timer);
  roles.update(() => ({ replay: null }));
}

/** The session's cost at time t (the last cost frame before it). */
export function costAt(r: Replay, t: number): number {
  let usd = 0;
  for (const c of r.meta.costs || []) {
    if (c.t > t) break;
    usd = Number(c.usd) || 0;
  }
  return usd;
}
