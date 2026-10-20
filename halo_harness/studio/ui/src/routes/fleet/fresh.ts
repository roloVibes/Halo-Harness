// A GET fleet answer never undoes a newer agent_state frame (3.1.5.0 R3
// follow-up, the Linux CI flake where the map kept a stopped agent
// "running"). The answer can be older than the moment it was asked for (the
// local view's 1 s snapshot cache and its socket probes), so a frame that
// landed after `asked - STALE_MS` is newer than the answer may be: that row
// stays as the frame left it, unless the answer's state is further along its
// life (queued, then running / waiting / paused, then done / failed /
// stopped), which only a newer source can know. An agent the frame added and
// the answer does not list yet is kept the same way. sync.ts notes each frame
// (`noteFrame`) and merges each answer (`keepFresh`).
import { keyOf } from "./store";
import type { AgentKey, AgentRow, Harness } from "./types";

export const STALE_MS = 2500;
const frameAt = new Map<AgentKey, number>();
const STAGE: Record<string, number> = { queued: 0, running: 1, waiting: 1, paused: 1, done: 2, failed: 2, stopped: 2 };

export function noteFrame(key: AgentKey, at = Date.now()): void {
  frameAt.set(key, at);
}

const further = (a: AgentRow, b: AgentRow) => (STAGE[String(a.state)] ?? 1) > (STAGE[String(b.state)] ?? 1);

/** `next` (a GET fleet answer asked for at `asked`) with the rows frames changed since it may have been read. */
export function keepFresh(prev: Harness[], next: Harness[], asked: number): Harness[] {
  const fresh = new Map<AgentKey, AgentRow>();
  for (const h of prev)
    for (const s of h.sessions || [])
      for (const a of s.agents || []) {
        const k = keyOf(h.id, s.session_id, a.agent_id);
        if ((frameAt.get(k) || 0) > asked - STALE_MS) fresh.set(k, a);
      }
  if (!fresh.size) return next;
  return next.map((h) => ({
    ...h,
    sessions: (h.sessions || []).map((s) => {
      const rows = s.agents || [];
      const seen = new Set(rows.map((a) => a.agent_id));
      const merged = rows.map((a) => {
        const f = fresh.get(keyOf(h.id, s.session_id, a.agent_id));
        return f && !further(a, f) ? { ...a, ...f } : a;
      });
      const added = [...fresh.entries()]
        .filter(([k, a]) => k.startsWith(`${h.id}|${s.session_id}|`) && !seen.has(a.agent_id))
        .map(([, a]) => a);
      return added.length || merged.some((a, i) => a !== rows[i]) ? { ...s, agents: [...merged, ...added] } : s;
    }),
  }));
}
