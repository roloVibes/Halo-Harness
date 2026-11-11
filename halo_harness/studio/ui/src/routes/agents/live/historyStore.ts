// Live's History (3.3.18.0 "The living canvas"): the past -- sessions of this harness, Orchestra runs of this repo,
// missions -- newest first, one row each: what it was, when it started, how long, its cost, how it ended. Read from the
// routes that already hold them (GET fleet/history?role=main, GET orchestra/runs, GET fleet/missions); what is live now
// is not a row (it is on the canvas). Loaded when Live shows and each time the drawer opens; a click on a row opens it
// as a replay (replay.ts). The drawer is closed on load and opens only on a click.
import { api } from "../../../lib/api";
import { createStore, useStore } from "../../../lib/store";
import { fleet } from "../../fleet/store";
import { FINAL, type Summary } from "../../fleet/mstore";
import { orch } from "../../orchestra/store";
import type { RunRow } from "../../orchestra/types";
import type { HistoryRun } from "../../roles/types";
import { harnessNow, LIVE_STATES } from "./now";
import type { HistoryKind } from "./replay";

export type HistoryRow = { kind: HistoryKind; id: string; what: string; when: number; secs: number | null; cost: number | null; how: string };
type State = { open: boolean; rows: HistoryRow[]; loaded: boolean; error: string };

export const history = createStore<State>({ open: false, rows: [], loaded: false, error: "" });
export const useHistory = <S,>(pick: (s: State) => S): S => useStore(history, pick);
export const toggleHistory = (on?: boolean) => {
  const open = on ?? !history.get().open;
  history.update(() => ({ open }));
  if (open) void loadHistory();
};

const num = (v: unknown): number | null => (typeof v === "number" && isFinite(v) ? v : null);

/** The sessions of this harness that are open now, and those with an agent at work. */
function openSessions(): { open: Set<string>; busy: Set<string> } {
  const open = new Set<string>(), busy = new Set<string>();
  for (const h of fleet.get().harnesses) {
    if (!h.local) continue;
    for (const s of h.sessions || []) {
      open.add(s.session_id);
      if (harnessNow(h) && (s.agents || []).some((a) => LIVE_STATES.includes(String(a.state || "")))) busy.add(s.session_id);
    }
  }
  return { open, busy };
}

/** The rows, newest first (pure: the three answers and what is live now). */
export function historyRows(sessions: HistoryRun[], runs: RunRow[], missions: Summary[], liveRun: string, open: Set<string>, busy: Set<string>): HistoryRow[] {
  const out: HistoryRow[] = [];
  for (const s of sessions) {
    const id = String(s.session_id || "");
    if (!id || busy.has(id)) continue;
    const t0 = num(s.started), t1 = num(s.finished);
    out.push({ kind: "session", id, what: String(s.task || "session " + id.slice(0, 8)), when: t0 || 0, secs: t0 && t1 && t1 > t0 ? t1 - t0 : null,
               cost: num(s.cost_usd), how: open.has(id) ? "open, nothing running" : "closed" });
  }
  for (const r of runs) {
    if (r.run_id === liveRun || r.state === "running") continue;
    out.push({ kind: "run", id: r.run_id, what: r.goal_what || "Orchestra run " + r.run_id, when: num(r.created) || 0, secs: null, cost: num(r.cost_usd),
               how: String(r.state || "?") });
  }
  for (const m of missions) {
    if (!FINAL.includes(m.state)) continue;
    const t1 = num(m.ended);
    out.push({ kind: "mission", id: m.id, what: m.goal || "mission " + m.id, when: num(m.created) || 0, secs: t1 && t1 > m.created ? t1 - m.created : null,
               cost: num(m.cost_usd), how: m.stop_reason ? `${m.state}: ${m.stop_reason}` : String(m.state) });
  }
  return out.map((r, i) => [r, i] as const).sort((a, b) => b[0].when - a[0].when || a[1] - b[1]).map(([r]) => r);
}

let asking = 0;
export async function loadHistory(): Promise<void> {
  const mine = ++asking;
  const [s, r, m] = await Promise.all([
    api.get<{ runs: HistoryRun[] }>("fleet/history", { role: "main", n: "20" }).then((x) => x.runs || []).catch(() => [] as HistoryRun[]),
    api.get<RunRow[]>("orchestra/runs").catch(() => [] as RunRow[]),
    api.get<{ missions: Summary[] }>("fleet/missions").then((x) => x.missions || []).catch(() => [] as Summary[]),
  ]);
  if (mine !== asking) return;
  const o = orch.get().data;
  const { open, busy } = openSessions();
  history.update(() => ({ rows: historyRows(s, Array.isArray(r) ? r : [], m, o?.live ? o.run.run_id : "", open, busy), loaded: true, error: "" }));
}
