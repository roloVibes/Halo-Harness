// TALK rows (3.3.16.2, the owner: "a section ... for model to model or agent to agent conversations ... its own
// label"): an `agent_talk` frame (fleet/talk.py: {id, from, to, text, why, re?, cut?, square?, machine?}) is one line
// of kind `talk` under its speaker, and one message of the Conversations panel (`talks`, the newest MAX_MSGS). The edge
// between the two agents on the map lights once, from the speaker to the listener (FleetEdges, kind `talk`).
// A hand-back is ONE row: when the speaker's OUT row ("done, its last words") is already there with nothing of its
// own after it, that row becomes the TALK row in place; an OUT that would come after a TALK hand-back is not added
// (liveFeed.ts `talkedBack`, liveTree.ts). The row is drawn as the hand-back block with `from -> to` on it.
import type { FeedFrame } from "../../lib/events";
import { createStore, useStore } from "../../lib/store";
import { findAgent, fleet, keyOf, localId } from "../fleet/store";
import type { AgentKey } from "../fleet/types";
import { addLine, live } from "./liveFeed";
import type { LiveLine, Talk } from "./liveTypes";

const MAX_MSGS = 600;
const TEXT_MAX = 4000;

export type TalkMsg = Talk & { text: string; ts: number; n: number };
type TalkState = { msgs: TalkMsg[] };
export const talks = createStore<TalkState>({ msgs: [] });
export const useTalks = <S,>(sel: (s: TalkState) => S): S => useStore(talks, sel);

const nameOf = (key: AgentKey, fallback: string) => {
  const r = key ? findAgent(fleet.get(), key) : null;
  return String(r?.a.name || r?.a.role || fallback || "?");
};

/** The pair a message belongs to, the same for both directions ("a|b" in key order). */
export const pairOf = (m: Pick<Talk, "fromKey" | "toKey" | "machine">) => {
  const b = m.toKey || "machine:" + (m.machine || "?");
  return m.fromKey < b ? `${m.fromKey}>${b}` : `${b}>${m.fromKey}`;
};

/** An OUT row of `key` that is its newest row: the hand-back takes its place. */
function outRow(lines: LiveLine[], key: AgentKey): number {
  for (let j = lines.length - 1; j >= Math.max(0, lines.length - 30); j--) {
    if (lines[j].key !== key) continue;
    return lines[j].kind === "output" ? j : -1;
  }
  return -1;
}

export function onTalk(f: FeedFrame): void {
  if (!f.session_id) return;
  const d = (f.data || {}) as Record<string, unknown>;
  const h = String(f.harness || localId(fleet.get()) || ""), sid = String(f.session_id || "");
  const from = String(d.from || f.agent_id || "main"), to = String(d.to || "");
  const fromKey = keyOf(h, sid, from), toKey = to ? keyOf(h, sid, to) : "";
  const talk: Talk = {
    id: String(d.id || ""), from, to, why: String(d.why || "task"), fromKey, toKey,
    fromName: String(d.from_name || "") || nameOf(fromKey, from), toName: String(d.to_name || "") || nameOf(toKey, to || String(d.machine || "")),
    ...(d.re ? { re: String(d.re) } : {}), ...(d.cut ? { cut: true, chars: Number(d.chars) || undefined } : {}),
    ...(d.square ? { square: String(d.square) } : {}), ...(d.machine ? { machine: String(d.machine) } : {}),
  };
  const text = String(d.text || "").slice(0, TEXT_MAX);
  const ts = Number(d.ts || f.ts) || Date.now() / 1000;
  let n = 0;
  const lines = live.get().lines;
  const j = talk.why === "hand-back" ? outRow(lines, fromKey) : -1;
  if (j >= 0) {
    const next = lines.slice();
    next[j] = { ...lines[j], kind: "talk", text, talk, state: "done" };
    n = next[j].n;
    live.update(() => ({ lines: next }));
  } else {
    addLine({ key: fromKey, kind: "talk", ts, text, talk, ...(talk.why === "hand-back" ? { state: "done" } : {}) });
    const all = live.get().lines;
    n = all[all.length - 1]?.n || 0;
  }
  talks.update((s) => ({ msgs: [...s.msgs, { ...talk, text, ts, n }].slice(-MAX_MSGS) }));
  if (toKey && findAgent(fleet.get(), fromKey) && findAgent(fleet.get(), toKey))
    fleet.update((st) => ({ edges: [...st.edges, { from: fromKey, to: toKey, ts: Date.now(), kind: "talk" as const }].slice(-40) }));
}
