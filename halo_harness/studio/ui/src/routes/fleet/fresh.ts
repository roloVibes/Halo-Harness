// A GET fleet answer never undoes a newer frame (3.1.5.0 R3 follow-up, the
// Linux CI flake where the map kept a stopped agent "running"; 3.1.8.0 R6
// the session's own figures too). The answer can be older than the moment
// it was asked for (the local view's 1 s snapshot cache and its socket
// probes), so a frame that landed after `asked - STALE_MS` is newer than the
// answer may be:
// - an agent row stays as its `agent_state` frame left it, unless the
//   answer's state is further along its life (queued, then running /
//   waiting / paused, then done / failed / stopped), which only a newer
//   source can know; an agent the frame added and the answer does not list
//   yet is kept the same way; its tokens are the higher of the two;
// - a session's figures (`message_end` / `status`, figures.ts) stay: the
//   higher spend, tokens and turns, the frame's context fill, and the
//   frame's phase as busy unless the answer says an ask waits.
// sync.ts notes each frame (`noteFrame`, `noteFigures`) and merges each
// answer (`keepFresh`).
import { agentWith, keepFigures } from "./figures";
import { keyOf } from "./store";
import type { AgentKey, AgentRow, Harness, SessionRow } from "./types";

export const STALE_MS = 2500;
const frameAt = new Map<AgentKey, number>();
const figuresAt = new Map<string, number>();
const phaseAt = new Map<string, { at: number; busy: boolean }>();
const STAGE: Record<string, number> = { queued: 0, running: 1, waiting: 1, paused: 1, done: 2, failed: 2, stopped: 2 };

export function noteFrame(key: AgentKey, at = Date.now()): void {
  frameAt.set(key, at);
}

/** A session's figures frame landed (`busy`: the phase it said, when it said one). */
export function noteFigures(h: string, sid: string, busy?: boolean, at = Date.now()): void {
  figuresAt.set(`${h}|${sid}`, at);
  if (typeof busy === "boolean") phaseAt.set(`${h}|${sid}`, { at, busy });
}

const further = (a: AgentRow, b: AgentRow) => (STAGE[String(a.state)] ?? 1) > (STAGE[String(b.state)] ?? 1);

function freshSessions(prev: Harness[], asked: number): Map<string, { had: SessionRow; phase: boolean | null }> {
  const out = new Map<string, { had: SessionRow; phase: boolean | null }>();
  for (const h of prev)
    for (const s of h.sessions || []) {
      const k = `${h.id}|${s.session_id}`;
      if ((figuresAt.get(k) || 0) <= asked - STALE_MS) continue;
      const p = phaseAt.get(k);
      out.set(k, { had: s, phase: p && p.at > asked - STALE_MS ? p.busy : null });
    }
  return out;
}

/** `next` (a GET fleet answer asked for at `asked`) with the rows and figures frames changed since it may have been read. */
export function keepFresh(prev: Harness[], next: Harness[], asked: number): Harness[] {
  const fresh = new Map<AgentKey, AgentRow>();
  for (const h of prev)
    for (const s of h.sessions || [])
      for (const a of s.agents || []) {
        const k = keyOf(h.id, s.session_id, a.agent_id);
        if ((frameAt.get(k) || 0) > asked - STALE_MS) fresh.set(k, a);
      }
  const figs = freshSessions(prev, asked);
  if (!fresh.size && !figs.size) return next;
  return next.map((h) => ({
    ...h,
    sessions: (h.sessions || []).map((s) => {
      const fig = figs.get(`${h.id}|${s.session_id}`);
      const base = fig ? keepFigures(s, fig.had, fig.phase) : s;
      const rows = s.agents || [];
      const seen = new Set(rows.map((a) => a.agent_id));
      const merged = rows.map((a) => {
        const f = fresh.get(keyOf(h.id, s.session_id, a.agent_id));
        return f && !further(a, f) ? agentWith(a, f) : a;
      });
      const added = [...fresh.entries()]
        .filter(([k, a]) => k.startsWith(`${h.id}|${s.session_id}|`) && !seen.has(a.agent_id))
        .map(([, a]) => a);
      return added.length || merged.some((a, i) => a !== rows[i]) ? { ...base, agents: [...merged, ...added] } : base;
    }),
  }));
}
