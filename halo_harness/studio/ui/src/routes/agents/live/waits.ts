// What each live agent is WAITING ON, and the session's waiting path (3.3.18.0 "The living canvas" part 3). One
// word-level fact per agent, derived from what the page already has -- the agent's row (state, current), the feed's open
// tool and its last lines (shared/liveFeed.ts) -- never invented:
//
//   you      it waits on you (state waiting: an ask, its words from its last ASK row) or it is paused
//   agent    its open tool is Agent / Task / Workflow and an agent it started still runs: that one (the one that waits on
//            you first, else the one with a tool, else the newest)
//   tool     a tool runs: which, and for how long (from its start on the feed; unknown when only the row says so)
//   model    nothing else runs and it is not writing: it waits on a model reply, for as long as since its last line
//   nothing  it is writing (a text line in the last WRITING_MS): working; or queued, not started
//
// The waiting path is the chain from main down to what the whole session waits for: an agent that waits on you anywhere
// first (the oldest), else main's own wait followed down through the agents it waits on. Pure.
import type { LiveNode } from "../../roles/liveModel";
import type { OpenTool } from "../../shared/liveFeed";
import type { LiveLine } from "../../shared/liveTypes";

export type WaitKind = "you" | "agent" | "tool" | "model" | "nothing";
export type Wait = { kind: WaitKind; what: string; since: number | null; who: string };
export const WRITING_MS = 4000;
const DELEGATES = ["Agent", "Task", "Workflow"];
const LIVE = ["queued", "running", "waiting", "paused"];

export const WAIT_WORD: Record<WaitKind, string> = { you: "you", agent: "an agent", tool: "a tool", model: "a model reply", nothing: "nothing" };

/** One agent's last lines: its newest line and its newest ASK row (from the feed's lines, newest last). */
export type Recent = { last: LiveLine | null; ask: LiveLine | null };

export function recentOf(lines: LiveLine[], keys: Set<string>): Map<string, Recent> {
  const out = new Map<string, Recent>();
  for (let i = lines.length - 1; i >= 0 && out.size < keys.size * 2; i--) {
    const l = lines[i];
    if (!keys.has(l.key)) continue;
    const r = out.get(l.key) || { last: null, ask: null };
    if (!r.last) r.last = l;
    if (!r.ask && (l.kind === "ask")) r.ask = l;
    out.set(l.key, r);
  }
  return out;
}

/** "Bash: pytest -q" -> "Bash pytest -q" (a row's `current` in words). */
const toolWords = (cur: string) => cur.replace(/^([A-Za-z_]+):\s*/, "$1 ").trim();

export function waitOf(n: LiveNode, open: OpenTool | null, r: Recent | undefined, kids: LiveNode[], now: number): Wait | null {
  if (!LIVE.includes(n.state) || n.virtual || n.kind || n.run) return null;
  if (n.state === "waiting") {
    const t = r?.ask?.text || "";
    return { kind: "you", what: t ? (/^asks /.test(t) ? `${n.name} ${t}` : `${n.name} asks: ${t}`) : `${n.name} asks you`, since: r?.ask ? r.ask.t0 : null, who: n.key };
  }
  if (n.state === "paused") return { kind: "you", what: `${n.name} is paused`, since: null, who: n.key };
  if (n.state === "queued") return { kind: "nothing", what: "queued, not started", since: null, who: n.key };
  const tool = open?.tool || (n.current && n.current !== "thinking" ? n.current.split(":")[0].trim() : "");
  if (DELEGATES.includes(tool)) {
    const live = kids.filter((k) => LIVE.includes(k.state));
    const pick = live.find((k) => k.state === "waiting") || live.find((k) => k.current && k.current !== "thinking") || live[live.length - 1];
    if (pick) return { kind: "agent", what: pick.role && pick.role !== pick.name ? pick.role : pick.name, since: open ? open.t0 : null, who: pick.key };
  }
  if (tool) return { kind: "tool", what: n.current && n.current.startsWith(tool) ? toolWords(n.current) : tool, since: open ? open.t0 : null, who: n.key };
  if (r?.last && r.last.kind === "text" && now - (r.last.ended || r.last.t0) < WRITING_MS) return { kind: "nothing", what: "working: writing", since: null, who: n.key };
  return { kind: "model", what: "a model reply", since: r?.last ? r.last.ended || r.last.t0 : n.started ? n.started * 1000 : null, who: n.key };
}

/** "42 s", "3 min 05 s" since `t0` (ms); "" when unknown. */
export function secsWords(t0: number | null, now: number): string {
  if (!t0) return "";
  const s = Math.max(0, Math.round((now - t0) / 1000));
  return s < 60 ? `${s} s` : `${Math.floor(s / 60)} min ${String(s % 60).padStart(2, "0")} s`;
}

export type WaitPath = { ids: string[]; leaf: LiveNode | null; wait: Wait | null };

/** The chain from the root to what the session waits for (ids in order), its last agent and that agent's wait. */
export function waitingPath(nodes: LiveNode[], waits: Map<string, Wait>): WaitPath {
  const byId = new Map(nodes.map((n) => [n.id, n]));
  const byKey = new Map(nodes.filter((n) => n.key).map((n) => [n.key, n]));
  const chain = (leaf: LiveNode) => { const ids: string[] = []; for (let x: LiveNode | undefined = leaf; x && !ids.includes(x.id); x = x.parent ? byId.get(x.parent) : undefined) ids.unshift(x.id); return ids; };
  const asks = nodes.filter((n) => waits.get(n.id)?.kind === "you").sort((a, b) => (waits.get(a.id)!.since || 0) - (waits.get(b.id)!.since || 0));
  if (asks.length) return { ids: chain(asks[0]), leaf: asks[0], wait: waits.get(asks[0].id)! };
  const root = nodes.find((n) => !n.parent && waits.has(n.id));
  if (!root) return { ids: [], leaf: null, wait: null };
  let cur = root;
  for (let i = 0; i < 24; i++) {
    const w = waits.get(cur.id);
    const next = w?.kind === "agent" ? byKey.get(w.who) || byId.get(w.who) : undefined; // 3.4.0.0 D: a run's lane by its id
    if (!next || !waits.has(next.id)) break;
    cur = next;
  }
  return { ids: chain(cur), leaf: cur, wait: waits.get(cur.id) || null };
}
