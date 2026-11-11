// Truth first (3.3.18.0 "The living canvas", the owner: "I always see like unused older version of orchestrations that
// aren't even happening ... I'd love to see what is actually happening"): what Live draws as PRESENT. Pure, plus the
// small set of failed agents the owner dismissed.
//
//   live      queued, running, waiting, paused: drawn
//   done      (or stopped) drawn for LINGER_MS after this page saw it finish (the green fades over those ten seconds),
//             then it leaves; one that finished before the page loaded is past: not drawn
//   failed    drawn until dismissed (its node's `dismiss`), when this page saw it fail; one that failed before the page
//             loaded is past: not drawn
//   a parent  of anything drawn is drawn (the tree keeps its spine); a session node while one of its agents is (or it is
//             busy with a turn, waits on you, or works for a running mission); a
//             group while one of its agents is (groups come from the drawn nodes); a machine always (the fleet is here)
//   a run     (an Orchestra run's lead and lanes) only while the run is live (runLanes.tsx)
//   a part    of a mission only while the mission runs or is being planned (useLiveNodes.ts)
//
// A harness counts while it is this one or online: an away member's last announce is not "now".
import { useMemo } from "react";
import { DONE_MS, useFleet } from "../../fleet/store";
import type { Harness } from "../../fleet/types";
import type { LiveNode } from "../../roles/liveModel";
import { createStore, useStore } from "../../../lib/store";

export const LINGER_MS = DONE_MS; // how long a finished agent stays on Live
export const LIVE_STATES = ["queued", "running", "waiting", "paused"];
const DONE = ["done", "stopped"];
const NO = new Set<string>();

/** The failed agents the owner dismissed from Live (their key); in memory, as Cast's acknowledged glow. */
const dismissed = createStore<{ keys: string[] }>({ keys: [] });
export const isDismissed = (key: string): boolean => dismissed.get().keys.includes(key);
export const useDismissed = (): string[] => useStore(dismissed, (s) => s.keys);
export function dismiss(key: string): void {
  if (key && !isDismissed(key)) dismissed.update((s) => ({ keys: [...s.keys, key] }));
}

/** A harness whose rows say what is happening now: this one, or a member that is online. */
export const harnessNow = (h: Pick<Harness, "local" | "online">): boolean => !!h.local || h.online !== false;

/** Is this one node present by itself (before its parents are added)? */
export function presentSelf(n: LiveNode, doneAt: Record<string, number>, now: number, gone: string[] = [], keep: Set<string> = NO): boolean {
  if (n.kind === "session") return n.state === "busy" || n.state === "waiting" || keep.has(n.sid || ""); // a turn, an ask, a running mission's
  if (n.kind === "machine" || n.virtual) return false;
  if (n.kind === "part" || n.run) return true;
  if (LIVE_STATES.includes(n.state)) return true;
  const at = doneAt[n.key] || 0;
  if (DONE.includes(n.state)) return !!at && now - at < LINGER_MS;
  if (n.state === "failed") return !!at && !gone.includes(n.key);
  return false;
}

/** The nodes Live draws now: the present ones and the parents, sessions and machines that hold them. */
export function present(nodes: LiveNode[], doneAt: Record<string, number>, now: number, gone: string[] = [], held: Set<string> = NO): LiveNode[] {
  const byId = new Map(nodes.map((n) => [n.id, n]));
  const keep = new Set<string>();
  for (const n of nodes) {
    if (!presentSelf(n, doneAt, now, gone, held)) continue;
    for (let x: LiveNode | undefined = n; x && !keep.has(x.id); x = x.parent ? byId.get(x.parent) : undefined) keep.add(x.id);
  }
  return nodes.filter((n) => keep.has(n.id) || n.kind === "machine");
}

/** The agents at work now across the harnesses that count (the rail's Agents badge). */
export function liveCount(harnesses: Harness[]): number {
  let n = 0;
  for (const h of harnesses) {
    if (!harnessNow(h)) continue;
    for (const s of h.sessions || []) for (const a of s.agents || []) if (LIVE_STATES.includes(String(a.state || ""))) n += 1;
  }
  return n;
}

export function useLiveCount(): number {
  const harnesses = useFleet((s) => s.harnesses);
  return useMemo(() => liveCount(harnesses), [harnesses]);
}

/** The session Live opens on: the one asked for while it is listed, else the newest with an agent at work, else the newest. */
export function pickSession(refs: { id: string; live: number }[], want: string): string {
  if (want && refs.some((r) => r.id === want)) return want;
  return (refs.find((r) => r.live > 0) || refs[0])?.id || "";
}
