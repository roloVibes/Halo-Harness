// The label on main's line into a block (3.3.18.0 "The living canvas" part 3): the plan's when, except in the moments
// after a hand-off on that line -- main's task to an agent of the block, or its hand-back to main (the 3.3.16.2 TALK
// messages, shared/liveTalk.ts) -- when the label says it in a few words, then goes back to the when. Hover: the last
// three exchanges on that line (the hover card). A click opens Session's Conversations on that pair.
import { useMemo } from "react";
import { HoverBody, type HoverRow } from "../../../lib/hover/HoverBody";
import { useHover } from "../../../lib/hover/useHover";
import { clock, short } from "../../orchestra/format";
import { useTalks, type TalkMsg } from "../../shared/liveTalk";
import { openConversation } from "../../session/convPick";
import type { PlanBox, PlanLine } from "./planLayout";
import { LABEL_W } from "./planLayout";
import { useLiveReplay } from "./replay";
import { talksAt } from "./timeline";

export const HANDOFF_MS = 8000; // how long a hand-off stays on its line
const WORD: Record<string, string> = { task: "task", square: "task", "hand-back": "back", steer: "steer", "hand-over": "over" };

/** The messages on the line between main (`root`) and the agents of a block, oldest first. */
export function lineTalks(msgs: TalkMsg[], root: string, keys: Set<string>): TalkMsg[] {
  return msgs.filter((m) => (m.fromKey === root && keys.has(m.toKey)) || (keys.has(m.fromKey) && m.toKey === root));
}

export function handoffWords(m: TalkMsg): string {
  return `${WORD[m.why] || m.why}: ${short(m.text.replace(/\s+/g, " "), 40)}`;
}

export function LineLabel({ l, b, root, now: wall, scale = 1 }: { l: PlanLine; b: PlanBox | undefined; root: string; now: number; scale?: number }) {
  const r = useLiveReplay(); // 3.4.1.0 R1: a replay's hand-offs up to the scrubber's moment (timeline.ts talksAt)
  const live = useTalks((s) => s.msgs);
  const msgs = useMemo(() => (r ? talksAt(r.tl, r.t) : live), [r, live]);
  const now = r ? r.t * 1000 : wall;
  const keys = useMemo(() => new Set((b?.members || []).map((m) => m.key).filter(Boolean)), [b]);
  const mine = useMemo(() => (root && keys.size ? lineTalks(msgs, root, keys) : []), [msgs, root, keys]);
  const last = mine[mine.length - 1];
  const fresh = last && now - last.ts * 1000 < HANDOFF_MS ? last : null;
  const rows: HoverRow[] = mine.slice(-3).reverse().map((m) => [`${clock(m.ts)} ${m.fromName} → ${m.toName}`, short(m.text, 160)]);
  const hv = useHover("when", `plan-line:${l.to}`, () => <HoverBody title={`main → ${b?.def.title || l.to}`} is={`When: ${l.label || "main delegates"}`} rows={rows}
                                                                      foot={last ? "A click opens this pair in Session's Conversations" : "No hand-off on this line yet"} />);
  const text = fresh ? handoffWords(fresh) : l.label;
  if (!text) return null;
  const other = last ? (last.fromKey === root ? last.toKey : last.fromKey) : "";
  return (
    <div className="pb-when mono" style={{ left: l.lx, top: l.ly, width: LABEL_W * scale }} data-testid="live-plan-when" data-to={l.to} data-handoff={fresh ? fresh.why : undefined}
         role="button" tabIndex={0} onClick={() => other && !r && openConversation(root, other)} title={hv.titles ? text : undefined} {...hv.props}>
      {text}
    </div>
  );
}
