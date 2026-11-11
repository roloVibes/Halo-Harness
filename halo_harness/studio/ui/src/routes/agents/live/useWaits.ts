// Live's waits, computed once per second for the drawn tree (3.3.18.0 "The living canvas" part 3; waits.ts says the
// rules): each agent's wait, the waiting path, kept in a small store so a node's "waits on" row and the path's hairline
// read it without the canvas laying out again. The store moves only when a fact moves (the JSON of the facts; a tool's
// running seconds are not a fact here, its start is).
import { useEffect, useMemo } from "react";
import { createStore, useStore } from "../../../lib/store";
import type { LiveNode } from "../../roles/liveModel";
import { live, useLive } from "../../shared/liveFeed";
import { startLiveTree } from "../../shared/liveTree"; // the feed's THINK and TALK frames too (the near rows, the hand-offs)
import { recentOf, waitingPath, waitOf, type Wait, type WaitPath } from "./waits";
import { orch } from "../../orchestra/store";
import { runWaitOf } from "../run/runWaits";

type State = { waits: Record<string, Wait>; path: string[]; leaf: string; json: string };
export const waitStore = createStore<State>({ waits: {}, path: [], leaf: "", json: "" });
export const useWaitOf = (id: string): Wait | undefined => useStore(waitStore, (s) => s.waits[id]);
export const useOnPath = (id: string | null | undefined): boolean => useStore(waitStore, (s) => !!id && s.path.includes(id));
export const usePathIds = (): string[] => useStore(waitStore, (s) => s.path);

/** The waits of `nodes` and the waiting path; `on` false (Session's thumbnail, a replay) leaves the store alone. */
export function useWaits(nodes: LiveNode[], now: number, on: boolean): { waits: Map<string, Wait>; path: WaitPath } {
  useEffect(() => startLiveTree(), []);
  const open = useLive((s) => s.open);
  const n = useLive((s) => s.lines.length);
  const out = useMemo(() => {
    const waits = new Map<string, Wait>();
    if (!on) return { waits, path: { ids: [], leaf: null, wait: null } as WaitPath };
    const keys = new Set(nodes.filter((x) => x.key).map((x) => x.key));
    const recent = recentOf(live.get().lines, keys);
    const kids = new Map<string, LiveNode[]>();
    for (const x of nodes) if (x.parent) kids.set(x.parent, [...(kids.get(x.parent) || []), x]);
    const run = orch.get().data; // 3.4.0.0 D: a goal run's boxes (run/runWaits.ts): the gate and the merge on the path
    for (const x of nodes) {
      const w = x.run ? runWaitOf(x, run) : waitOf(x, x.key ? open[x.key] || null : null, recent.get(x.key), kids.get(x.id) || [], now);
      if (w) waits.set(x.id, w);
    }
    return { waits, path: waitingPath(nodes, waits) };
    // eslint-disable-next-line react-hooks/exhaustive-deps -- `n` stands for the lines (a new line can change a wait)
  }, [nodes, open, n, now, on]);
  useEffect(() => {
    if (!on) return;
    const waits = Object.fromEntries(out.waits);
    const json = JSON.stringify([waits, out.path.ids]);
    if (json !== waitStore.get().json) waitStore.update(() => ({ waits, path: out.path.ids, leaf: out.path.leaf?.id || "", json }));
  }, [out, on]);
  useEffect(() => () => (on ? waitStore.update(() => ({ waits: {}, path: [], leaf: "", json: "" })) : undefined), [on]);
  return out;
}
