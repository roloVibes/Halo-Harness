// THINK rows (3.3.16.2, the owner: "make watching a model think much better"): an agent's `thinking_chunk` frames
// (fleet/think.py: one id per thought, the text in pieces, `end` with `ms` when it acted, `tokens` at message_end)
// grow ONE line of kind `thinking`, updated in place (only that row redraws; the list keeps every other line object).
// `linkThoughts` reads the list once per change: each action row (a tool call, the text it wrote, its hand-back, its
// words to another agent) after a thought of the same agent is that thought's act -- the `why?` chip opens the
// thought under it, the THINK row's chip says what it led to ("then ran Edit basket.py", "then answered").
import type { FeedFrame } from "../../lib/events";
import { fleet, keyOf, localId } from "../fleet/store";
import type { AgentKey } from "../fleet/types";
import { addLine, live, thinkSeen } from "./liveFeed";
import type { LiveLine } from "./liveTypes";

const THINK_MAX = 12000; // a thought's text kept here (the transcript keeps it whole)
const ACTS = new Set(["tool", "text", "output", "talk"]);

const keep = (t: string) => (t.length > THINK_MAX ? t.slice(0, THINK_MAX) + " ..." : t);

/** One `thinking_chunk` frame: the thought's row grows (or starts). */
export function onThink(f: FeedFrame): void {
  if (!f.session_id) return;
  const d = (f.data || {}) as { id?: string; text?: string; end?: boolean; ms?: number; tokens?: number };
  const key: AgentKey = keyOf(String(f.harness || localId(fleet.get()) || ""), String(f.session_id || ""), String(f.agent_id || "main"));
  const tid = String(d.id || "");
  const text = String(d.text || "");
  const now = Date.now();
  thinkSeen.add(key);
  const s = live.get();
  for (let j = s.lines.length - 1; j >= Math.max(0, s.lines.length - 400); j--) {
    const x = s.lines[j];
    if (x.key !== key || x.kind !== "thinking" || x.tid !== tid) continue;
    const lines = s.lines.slice();
    lines[j] = { ...x, text: keep(x.text + text), ended: now, ...(d.end ? { done: true } : {}),
                 ...(typeof d.ms === "number" ? { ms: d.ms } : {}), ...(typeof d.tokens === "number" ? { tokens: d.tokens } : {}) };
    live.update(() => ({ lines }));
    return;
  }
  if (!text && !d.end) return;
  addLine({ key, kind: "thinking", ts: Number(f.ts) || now / 1000, text: keep(text), tid, ended: now, done: !!d.end,
            ...(typeof d.ms === "number" ? { ms: d.ms } : {}), ...(typeof d.tokens === "number" ? { tokens: d.tokens } : {}) });
}

export type Links = {
  /** an action row's n -> the THINK row before it */
  thoughtOf: Map<number, LiveLine>;
  /** a THINK row's n -> the rows it led to */
  led: Map<number, LiveLine[]>;
};

/** Thought, then act: each agent's action rows after its THINK row (until its next thought, a steer or an ask). */
export function linkThoughts(lines: LiveLine[]): Links {
  const open = new Map<AgentKey, LiveLine>();
  const thoughtOf = new Map<number, LiveLine>();
  const led = new Map<number, LiveLine[]>();
  for (const l of lines) {
    if (l.kind === "thinking") {
      open.set(l.key, l);
      led.set(l.n, []);
    } else if (ACTS.has(l.kind)) {
      const t = open.get(l.key);
      if (t) {
        thoughtOf.set(l.n, t);
        led.get(t.n)!.push(l);
      }
    } else if (l.kind === "you" || l.kind === "ask" || l.kind === "asked") open.delete(l.key);
  }
  return { thoughtOf, led };
}

/** What a thought led to, in a few plain words ("then ran Edit basket.py", "then answered", "then spoke to main"). */
export function ledWords(first: LiveLine | undefined, count = 1): string {
  if (!first) return "";
  const more = count > 1 ? ` (+${count - 1})` : "";
  if (first.kind === "tool") return `then ran ${first.tool || "a tool"}${first.target ? " " + first.target.split(/[\\/]/).pop() : ""}${more}`;
  if (first.kind === "talk") return `then spoke to ${first.talk?.toName || "an agent"}${more}`;
  if (first.kind === "output") return `then handed back${more}`;
  return `then answered${more}`;
}

/** The thought's suffix once it ended: how long and how many tokens ("thought 4.2 s · 812 tokens"). */
export function thoughtTook(l: LiveLine): string {
  if (!l.done) return "";
  const parts: string[] = [];
  if (typeof l.ms === "number" && l.ms > 0) parts.push(l.ms < 1000 ? `${l.ms} ms` : `${(l.ms / 1000).toFixed(1)} s`);
  if (typeof l.tokens === "number" && l.tokens > 0) parts.push(`${l.tokens} tokens`);
  return parts.length ? "thought " + parts.join(" · ") : "";
}
