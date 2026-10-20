// What the agent tree adds to the Live column (3.1.5.0 R3; the feed's own
// lines are liveFeed.ts): read off the Fleet store on every change, so a GET
// and a frame count alike. A new agent under a parent is a spawn line; an
// agent that finishes hands its last text back as an output block; failed,
// waiting and paused are state lines; a steer sent from Studio (the
// stream's `you` entry) is echoed; a running tool row takes its target from
// the row's `current` ("Bash: git status"). While the Live panel shows
// (`seedBacklog`), each live agent of this harness has its backlog read once
// (`agent_tail`, streams.ts) and its last entries put in by time, before
// anything it did live. The first look at the tree is silent: what was
// already there is not news.
import { allAgents, fleet, isLive, localId } from "../fleet/store";
import { loadTail } from "../fleet/streams";
import type { AgentKey } from "../fleet/types";
import { addLine, fromEntry, live, startLive } from "./liveFeed";

const BACKLOG = 40;
const states = new Map<AgentKey, string>();
const yous = new Map<AgentKey, number>();
const seeded = new Set<AgentKey>();
let primed = false;
let seeding = false;

const nameOf = (a: { name?: string | null; role?: string | null; agent_id: string }) => a.name || a.role || a.agent_id;

let seenTree: unknown = null;
let seenStreams: unknown = null;

function onTree(): void {
  const s = fleet.get();
  if (!s.loaded) return;
  if (s.harnesses === seenTree && s.streams === seenStreams) return; // a hover or a pin: nothing here changed
  seenTree = s.harnesses;
  seenStreams = s.streams;
  const now = Date.now() / 1000;
  const here = localId(s);
  for (const r of allAgents(s)) {
    const st = String(r.a.state || "");
    const was = states.get(r.key);
    states.set(r.key, st);
    if (!primed || was === st) continue;
    if (was === undefined && r.a.parent) {
      const parent = (r.s.agents || []).find((x) => x.agent_id === r.a.parent);
      addLine({ key: r.key, kind: "spawn", ts: now, text: `${parent ? nameOf(parent) + " spawned it" : "spawned"}${r.a.task ? ": " + r.a.task : ""}` });
    } else if (st === "done" && was) {
      const said = live.get().lines.slice(-60).some((l) => l.key === r.key && l.kind === "output");
      if (!said) addLine({ key: r.key, kind: "output", ts: now, text: String(r.a.last_text || "done"), state: "done" });
    } else if ((st === "failed" || st === "waiting" || st === "paused" || st === "stopped") && was && !(st === "waiting" && askedNow(r.key))) {
      const text = st === "waiting" ? "waits on you" : st === "paused" ? "paused: holds at its next step" : st === "stopped" ? "stopped" : `failed${r.a.last_text ? ": " + r.a.last_text : ""}`;
      addLine({ key: r.key, kind: st === "failed" ? "error" : "state", ts: now, text: text.slice(0, 300), state: st });
    }
  }
  primed = true;
  targets(s);
  echoes(s);
  if (seeding) backlog(s, here);
}

/** An ask card of `key` just landed: its "waits on you" line would say it twice. */
const askedNow = (key: AgentKey) => live.get().lines.slice(-12).some((l) => l.key === key && l.kind === "ask" && Date.now() - l.t0 < 8000);

/** A running tool row takes its target from the agent row's `current` ("Bash: git status"). */
function targets(s: ReturnType<typeof fleet.get>): void {
  const open = live.get().open;
  const keys = Object.keys(open);
  if (!keys.length) return;
  const patch: Record<number, string> = {};
  for (const r of allAgents(s)) {
    const o = open[r.key];
    const cur = String(r.a.current || "");
    if (!o || !cur.startsWith(o.tool + ":")) continue;
    const line = [...live.get().lines].reverse().find((l) => l.key === r.key && l.kind === "tool" && !l.ended);
    if (line && !line.target) patch[line.n] = cur.slice(o.tool.length + 1).trim();
  }
  if (Object.keys(patch).length) live.update((st) => ({ lines: st.lines.map((l) => (patch[l.n] ? { ...l, target: patch[l.n] } : l)) }));
}

const ticks = new Map<AgentKey, number>();

/** A steer typed in Studio: the stream echoes it (`you`), and so does the column (only streams that moved are read). */
function echoes(s: ReturnType<typeof fleet.get>): void {
  for (const [key, st] of Object.entries(s.streams)) {
    if (ticks.get(key) === st.tick) continue;
    ticks.set(key, st.tick);
    const mine = st.entries.filter((e) => e.you);
    const seen = yous.has(key) ? yous.get(key)! : mine.length;
    yous.set(key, mine.length);
    for (const e of mine.slice(seen)) addLine({ key, kind: "you", ts: Number(e.ts) || Date.now() / 1000, text: String(e.text || "") });
  }
}

/** Each live agent of this harness: its backlog once, then its entries before its first live line. */
function backlog(s: ReturnType<typeof fleet.get>, here: string): void {
  for (const r of allAgents(s)) {
    if (r.h.id !== here || seeded.has(r.key)) continue;
    const st = s.streams[r.key];
    if (!st?.loaded) {
      if (isLive(r.a) && !st?.loading) void loadTail(r.key);
      continue;
    }
    seeded.add(r.key);
    const first = live.get().lines.find((l) => l.key === r.key)?.ts ?? Infinity;
    for (const e of st.entries.filter((x) => !x.you && (Number(x.ts) || 0) < first).slice(-BACKLOG)) fromEntry(r.key, e, true);
  }
}

let treeOn = false;

/** Start the column's sources (idempotent): the feed's (liveFeed.ts), then the tree's; `seed` turns the backlog reading on (the Live panel shows). */
export function startLiveTree(seed = false): void {
  startLive();
  if (!treeOn) {
    treeOn = true;
    fleet.subscribe(onTree);
    onTree();
  }
  if (seed && !seeding) {
    seeding = true;
    seenTree = null; // read the tree again now: the backlogs start
    window.setTimeout(onTree, 0);
  }
}
