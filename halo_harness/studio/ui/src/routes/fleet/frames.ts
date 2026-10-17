// Live Roles: what the shell knows about every live agent, put into the
// Roles store for the React canvas (3.0.7.0 R2: no framed page, nothing
// posted to a frame any more; routes/roles/live.ts matches each agent to its card).
// `liveRows` is every live agent (and one that just finished) with what it is
// doing right now; `useRolesLive` writes it into the store 120 ms after a
// fleet change and once a second (a done sweep or a typing glow ages out).
// While a canvas replay plays (routes/roles/Replay.tsx) the replay's agents
// stand in for these; the live rows keep arriving underneath.
import { useEffect } from "react";
import { short } from "../orchestra/format";
import { roles } from "../roles/store";
import { allAgents, fleet, isLive, sessionTitle, toolOf, type FleetState } from "./store";
import { startFleet } from "./sync";
import type { AgentRef } from "./types";

export type LiveRow = {
  key: string; harness: string; local: boolean; session: string; session_id: string; agent_id: string; parent: string | null;
  name: string; role: string; bio: string; lineup: string; model: string; state: string; task: string; current: string;
  last_text: string; cost_usd: number; since: number; activity: string; tool: string; calls: number; control: string;
};

const RECENT_MS = 3000;
const ACT_MS = 4000;

/** typing | tool | waiting | working | queued | done | failed: the card's glow (live.css). */
function activityOf(r: AgentRef, s: FleetState, now: number): string {
  const st = String(r.a.state || "");
  const act = s.activity[r.key];
  if (st === "waiting" || st === "paused") return "waiting";
  if (st === "failed") return "failed";
  if (st === "done" || st === "stopped") return "done";
  if (st === "queued") return "queued";
  if (act && now - act.ts < ACT_MS) return act.kind;
  return r.a.current && r.a.current !== "thinking" ? "tool" : "typing";
}

export function liveRows(s: FleetState): LiveRow[] {
  const now = Date.now();
  return allAgents(s)
    .filter((r) => isLive(r.a) || now - (s.doneAt[r.key] || 0) < RECENT_MS)
    .map((r) => ({
      key: r.key, harness: r.h.name || r.h.id.slice(0, 8), local: !!r.h.local, session: sessionTitle(r.s),
      session_id: r.s.session_id, agent_id: r.a.agent_id, parent: r.a.parent || null, name: r.a.name || r.a.agent_id,
      role: r.a.role || "", bio: r.a.bio || "", lineup: r.a.lineup || "", model: r.a.model || "", state: String(r.a.state || ""),
      task: r.a.task || "", current: r.a.current || "", last_text: short(r.a.last_text, 160), cost_usd: Number(r.a.cost_usd) || 0,
      since: Number(r.a.since) || 0, activity: activityOf(r, s, now), tool: toolOf(r.a, s.activity[r.key]),
      calls: s.activity[r.key]?.calls || 0, control: r.h.allow_control || "all",
    }));
}

export function useRolesLive(): void {
  useEffect(() => {
    let last = "";
    let timer = 0;
    startFleet();
    const push = () => {
      const rows = liveRows(fleet.get());
      const json = JSON.stringify(rows);
      if (json === last) return;
      last = json;
      roles.update(() => ({ live: rows }));
    };
    const unsub = fleet.subscribe(() => {
      window.clearTimeout(timer);
      timer = window.setTimeout(push, 120);
    });
    const tick = window.setInterval(push, 1000);
    push();
    return () => {
      unsub();
      window.clearInterval(tick);
      window.clearTimeout(timer);
    };
  }, []);
}
