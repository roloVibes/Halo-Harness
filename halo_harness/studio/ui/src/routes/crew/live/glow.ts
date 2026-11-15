// An agent's glow state (3.1.5.0 R3; 3.6.0.0 R5: Cast's cards went, the words stay for the Map's boxes and the live
// nodes): working while it types or runs a tool, waiting on you, done, failed. A failed agent the person dismissed
// (the Map drawer's Dismiss) is acknowledged here, so nothing keeps calling it out.
import type { LiveAgent } from "../models/types";

export type GlowState = "working" | "waiting" | "done" | "failed";

/** An agent's activity as its glow state; "" for no glow (nothing, or only queued). */
export function glowOf(activity: string): GlowState | "" {
  if (activity === "typing" || activity === "tool" || activity === "working") return "working";
  if (activity === "waiting" || activity === "done" || activity === "failed") return activity;
  return "";
}

const acked = new Set<string>();

/** Dismissed: its failed agents stop being called out. */
export function ackFailed(list: Pick<LiveAgent, "key" | "state">[]): void {
  for (const a of list) if (a.state === "failed") acked.add(a.key);
}

export const isAcked = (key: string) => acked.has(key);
