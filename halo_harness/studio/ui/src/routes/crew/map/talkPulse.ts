// Agents talking on the lit Map (3.6.0.0 R4b, R4's gap 7): an `agent_talk` frame (shared/liveTalk.ts) between two agents
// of the lit session whose boxes differ lights a short dashed pulse between their boxes for TALK_S seconds, with the
// first words on a small label -- no line is added to the map. Timed from when this page heard it (the row's arrival,
// `t0`), as the hand-off pulses are. Reduced motion: the two boxes are marked, nothing travels (map-lit.css).
import type { LiveLine } from "../../shared/liveTypes";
import type { TalkMsg } from "../../shared/liveTalk";
import { firstLevel, type Overlay } from "./overlay";
import { helperId } from "./litView";

export const TALK_S = 4;
export type TalkPulse = { from: string; to: string; text: string; n: number };

/** The agent id -> the box it is drawn in (a helper's own helpers: their first-level helper's box). `rows`: a run drawing
 *  (3.6.0.2 R15), where every child is a row inside the box that holds it (`ov.kids`), never a box of its own. */
export function boxOfAgent(ov: Overlay, rows = false): Map<string, string> {
  const out = new Map<string, string>();
  for (const [id, b] of Object.entries(ov.boxes)) for (const a of b.agents) out.set(a, id);
  if (rows) {
    for (const [id, ks] of Object.entries(ov.kids || {})) for (const k of ks) if (!out.has(k.aid)) out.set(k.aid, id);
    return out;
  }
  const top = new Set(firstLevel(ov.helpers).map((h) => h.aid));
  const up = (aid: string, depth = 0): string => {
    if (top.has(aid)) return helperId(aid);
    const h = ov.helpers.find((x) => x.aid === aid);
    return h && depth < 24 ? up(h.parent, depth + 1) || h.box : "";
  };
  for (const h of ov.helpers) out.set(h.aid, up(h.aid));
  return out;
}

/** The talks of session `sid` heard in the last TALK_S seconds (`now` in seconds), box to box. */
export function talkPulses(msgs: TalkMsg[], lines: LiveLine[], ov: Overlay | null, sid: string, now: number, rows = false): TalkPulse[] {
  if (!ov || !sid) return [];
  const boxes = boxOfAgent(ov, rows);
  const out: TalkPulse[] = [];
  for (const m of msgs.slice(-40)) {
    if (!m.fromKey.includes(`|${sid}|`)) continue;
    const line = lines.find((l) => l.n === m.n);
    const heard = (line?.t0 || 0) / 1000;
    if (!heard || now - heard > TALK_S || heard - now > 1) continue;
    const from = boxes.get(m.from) || "", to = boxes.get(m.to) || "";
    if (!from || !to || from === to) continue;
    const words = m.text.replace(/\s+/g, " ").trim();
    out.push({ from, to, text: words.length > 48 ? words.slice(0, 45) + "..." : words, n: m.n });
  }
  return out;
}
