// What an agent is doing right now, from the fleet's frames (3.0.7.0 R2; 3.6.0.0 R5: Cast's cards went, the live nodes
// and Session read it): `activityOf` is its activity (typing, a tool, waiting, ...); `useStartFleet` starts the fleet's
// reads with the shell.
import { useEffect } from "react";
import type { FleetState } from "./store";
import { startFleet } from "./sync";
import type { AgentRef } from "./types";

export type LiveRow = {
  key: string; harness: string; local: boolean; session: string; session_id: string; agent_id: string; parent: string | null;
  name: string; role: string; bio: string; lineup: string; model: string; model_reason: string; state: string; task: string; current: string;
  last_text: string; cost_usd: number; since: number; activity: string; tool: string; calls: number; control: string;
};

const ACT_MS = 4000;

/** typing | tool | waiting | working | queued | done | failed: the card's glow (live.css). */
export function activityOf(r: AgentRef, s: FleetState, now: number): string {
  const st = String(r.a.state || "");
  const act = s.activity[r.key];
  if (st === "waiting" || st === "paused") return "waiting";
  if (st === "failed") return "failed";
  if (st === "done" || st === "stopped") return "done";
  if (st === "queued") return "queued";
  if (act && now - act.ts < ACT_MS) return act.kind;
  return r.a.current && r.a.current !== "thinking" ? "tool" : "typing";
}

/** 3.6.0.0 R5 (Cast's cards went; nothing reads a copy of the agents any more): the fleet starts with the shell. */
export function useStartFleet(): void {
  useEffect(() => startFleet(), []);
}
