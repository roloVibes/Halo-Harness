// An ask's line in the Feed (liveFeed.ts keeps the list): from its frame (one of the four ask events), or handed by the door
// of an ask (P9 batch 2, CI on the 3.6.0.2 candidate: glance/openAsk.ts, an agent on no box). That door says "its question
// is in the Feed", so the Feed shows it at that moment, built from the attention row the door was opened with (the agent's
// key, the row's own words; its choices are the row's keys: session/LiveRows.tsx AskCard), even when no frame of that
// agent has reached the page yet. The frame that brings the same ask later fills that row instead of drawing a second.
import type { AttnRow } from "../fleet/pstore";
import type { AgentKey } from "../fleet/types";
import type { LiveLine } from "./liveTypes";

const ASK_LABEL: Record<string, string> = { permission_request: "asks to run", question: "asks you", plan_review: "has a plan for you to review", approval_request: "asks for your approval" };
const ASK_KIND: Record<string, string> = { permission_request: "permission", question: "question", plan_review: "plan", approval_request: "approval" };
/** The four frames an ask comes as. */
export const ASK_EVENTS = Object.keys(ASK_LABEL);

export type AskLine = Pick<LiveLine, "kind" | "ts" | "text" | "ask" | "id" | "handed">;
export type RowAsk = Pick<AttnRow, "kind" | "what" | "detail" | "since" | "target">;

/** The line an ask frame (`event`, its data `d`, its time) makes. */
export function askOfFrame(event: string, d: Record<string, unknown>, ts: number): AskLine {
  const input = (d.input && typeof d.input === "object" ? d.input : {}) as Record<string, unknown>;
  const what = String(input.question || d.question || d.text || input.command || d.name || "").replace(/\s+/g, " ").slice(0, 220);
  return { kind: "ask", ts, text: `${ASK_LABEL[event] || "asks"}${what ? ": " + what : ""}`, ask: ASK_KIND[event] || event, id: String(d.id || "") };
}

/** The line the door hands the Feed: the attention row's words, its kind, its request's id ("" for an agent that waits). */
export function askOfRow(r: RowAsk): AskLine {
  const text = [r.what, r.detail].filter(Boolean).join(" · ");
  return { kind: "ask", ts: r.since || Date.now() / 1000, text, ask: r.kind, id: String(r.target?.request_id || ""), handed: true };
}

const asksOf = (l: LiveLine, key: AgentKey) => l.key === key && l.kind === "ask";

/** `lines` with ask `a` of agent `key` in. Handed: nothing changes when the Feed already has that ask (an ask of that agent
 *  with its id; with no id, any ask of that agent). A frame: it fills the handed row it brings (the same id, or a handed
 *  row with none), once; else it is a row of its own. A new row is appended with `next()`'s number and clock. */
export function withAsk(lines: LiveLine[], key: AgentKey, a: AskLine, next: () => Pick<LiveLine, "n" | "t0">): LiveLine[] {
  const add = () => [...lines, { ...next(), key, ...a }];
  if (a.handed) return lines.some((x) => asksOf(x, key) && (!a.id || x.id === a.id)) ? lines : add();
  const at = lines.findIndex((x) => asksOf(x, key) && !!x.handed && (!x.id || x.id === a.id));
  if (at < 0) return add();
  const out = lines.slice();
  out[at] = { ...lines[at], ...a, handed: false };
  return out;
}
