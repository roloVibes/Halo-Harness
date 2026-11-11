// A replay on Live (3.3.18.0 "The living canvas"): something past -- a session, an Orchestra run, a mission -- opened
// from the History drawer (History.tsx) and drawn on Live's canvas as it ended, muted, under a "replay -- ended <when>"
// banner (ReplayBanner.tsx); "Back to now" clears it. Nothing past reaches the canvas any other way. The nodes are built
// here from what the routes answer (GET fleet/replay, GET orchestra/<run>, GET fleet/missions/<id>); none is a live
// agent, so no key, no glow, no steer.
import { api, ApiError } from "../../../lib/api";
import { createStore, toast, useStore } from "../../../lib/store";
import { partState, type View } from "../../fleet/mstore";
import type { RunPayload } from "../../orchestra/types";
import type { LiveNode } from "../../roles/liveModel";
import type { ReplayMeta } from "../../roles/types";
import { runNodes } from "./runLanes";

export type HistoryKind = "session" | "run" | "mission";
export type LiveReplay = { kind: HistoryKind; id: string; title: string; ended: number | null; nodes: LiveNode[] };

export const liveReplay = createStore<{ r: LiveReplay | null; busy: string }>({ r: null, busy: "" });
export const useLiveReplay = (): LiveReplay | null => useStore(liveReplay, (s) => s.r);

const BLANK = { key: "", pick: "", activity: "", glow: "" as const, card: "", cardLabel: "", current: "", model: "", role: "", task: "",
  cost: null, started: null, ended: null };
const num = (v: unknown): number | null => (typeof v === "number" && isFinite(v) ? v : null);
const str = (v: unknown): string => (v == null ? "" : String(v));

/** A session's agents as it ended (GET fleet/replay's `agents`). */
export function sessionNodes(meta: ReplayMeta): LiveNode[] {
  const ids = new Set((meta.agents || []).map((a) => str(a.agent_id)));
  return (meta.agents || []).map((a) => {
    const parent = str(a.parent);
    return { ...BLANK, id: str(a.agent_id), parent: parent && ids.has(parent) ? parent : null, name: str(a.name || a.agent_id), role: str(a.role),
             model: str(a.model), state: str(a.state || "done"), task: str(a.task), cost: num(a.cost_usd), started: num(a.since), ended: num(a.ended) };
  });
}

/** A run's lead and lanes as they ended. */
export function runReplayNodes(data: RunPayload): LiveNode[] {
  return runNodes({ ...data, live: true }).map((n) => ({ ...n, glow: "" as const, state: n.id.includes(":lane:") ? n.state : str(data.run.state) }));
}

/** A mission's parts as they ended, under one node for the mission. */
export function missionNodes(v: View): LiveNode[] {
  const root = `mission:${v.mission.id}`;
  const out: LiveNode[] = [{ ...BLANK, id: root, parent: null, name: "mission", role: "mission", state: str(v.mission.state), task: str(v.summary?.goal),
                             cost: num(v.summary?.cost_usd), started: num(v.summary?.created), ended: num(v.summary?.ended) }];
  for (const p of v.plan?.parts || []) {
    const run = v.mission.parts?.[p.id];
    out.push({ ...BLANK, id: `${root}:${p.id}`, parent: root, name: str(p.title), role: str(p.kind), state: partState(v, p.id), task: str(p.brief),
               cost: num(run?.cost_usd), started: num(run?.started), ended: num(run?.ended) });
  }
  return out;
}

/** Open a past thing as a replay on Live. */
export async function openLiveReplay(kind: HistoryKind, id: string, title: string): Promise<boolean> {
  liveReplay.update(() => ({ busy: `${kind}:${id}` }));
  try {
    let nodes: LiveNode[] = [];
    let ended: number | null = null;
    if (kind === "session") {
      const meta = await api.get<ReplayMeta>("fleet/replay", { session: id, harness: "local" });
      nodes = sessionNodes(meta);
      ended = num(meta.ended);
    } else if (kind === "run") {
      const data = await api.get<RunPayload>(`orchestra/${encodeURIComponent(id)}`);
      nodes = runReplayNodes(data);
      ended = num(data.report?.ts) ?? num(data.run.created);
    } else {
      const v = await api.get<View>(`fleet/missions/${encodeURIComponent(id)}`);
      nodes = missionNodes(v);
      ended = num(v.summary?.ended) ?? num(v.summary?.updated);
    }
    if (!nodes.length) {
      toast("Nothing to replay: it left no agents", "info", 4000);
      return false;
    }
    liveReplay.update(() => ({ r: { kind, id, title, ended, nodes } }));
    return true;
  } catch (e) {
    toast(`No replay: ${e instanceof ApiError ? e.message : String(e)}`, "error", 5000);
    return false;
  } finally {
    liveReplay.update(() => ({ busy: "" }));
  }
}

/** Back to now: the replay leaves the canvas. */
export function backToNow(): void {
  liveReplay.update((s) => (s.r ? { r: null } : {}));
}
