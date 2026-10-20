// Spend over time for Session's Cost panel (3.1.5.0 R3): every session row's
// `cost_usd` as the Fleet store holds it (GET fleet and its feed), sampled
// when it changes and at least every SAMPLE_MS while it does not, so the
// sparkline's time axis stays honest through a quiet stretch. Kept per
// session (MAX samples) while the page is open; nothing is stored.
import { createStore, useStore } from "../../lib/store";
import { fleet } from "../fleet/store";

export type Sample = { t: number; usd: number; turns: number };
type SpendState = { series: Record<string, Sample[]> };

const MAX = 240;
const SAMPLE_MS = 5000;

export const spend = createStore<SpendState>({ series: {} });

export function useSpend(sid: string): Sample[] {
  return useStore(spend, (s) => s.series[sid] || NONE);
}

const NONE: Sample[] = [];
let started = false;

function sample(): void {
  const now = Date.now();
  const cur = spend.get().series;
  let next: Record<string, Sample[]> | null = null;
  for (const h of fleet.get().harnesses)
    for (const ss of h.sessions || []) {
      const usd = Number(ss.cost_usd) || 0;
      const turns = Number(ss.turns) || 0;
      const list = cur[ss.session_id] || NONE;
      const last = list[list.length - 1];
      if (last && last.usd === usd && last.turns === turns && now - last.t < SAMPLE_MS) continue;
      next = next || { ...cur };
      next[ss.session_id] = [...list, { t: now, usd, turns }].slice(-MAX);
    }
  if (next) spend.update(() => ({ series: next! }));
}

/** Start once (the Cost panel): a sample on every fleet change and every SAMPLE_MS. */
export function startSpend(): void {
  if (started) return;
  started = true;
  fleet.subscribe(sample);
  window.setInterval(sample, SAMPLE_MS);
  sample();
}

/** What the last finished turn cost: the spend between the two newest turn changes (null before two). */
export function lastTurnCost(list: Sample[]): number | null {
  const marks: Sample[] = [];
  for (let i = list.length - 1; i > 0 && marks.length < 2; i--) if (list[i].turns !== list[i - 1].turns) marks.push(list[i]);
  return marks.length === 2 ? Math.max(0, marks[0].usd - marks[1].usd) : null;
}
