// A live agent's "waits on" row (3.3.18.0 "The living canvas" part 3; waits.ts says the rules): one fact in a fixed row
// of its own -- WAITS, then you / a tool / a model reply / an agent / nothing, then what and for how long. Its seconds
// tick here only (the node's other rows never move for it).
import { useNow } from "../../fleet/store";
import { useWaitOf } from "./useWaits";
import { secsWords, WAIT_WORD } from "./waits";

export const WAITS_H = 18; // the row's height: Live's nodes grow by it (liveLayout's `extra`)

export function WaitsRow({ id }: { id: string }) {
  const w = useWaitOf(id);
  const now = useNow(!!w?.since, 1000);
  if (!w) return <div className="rlm-waits mono" aria-hidden="true" />;
  const secs = secsWords(w.since, now);
  const what = w.kind === "you" || w.kind === "model" ? (w.kind === "you" ? w.what : "") : w.what;
  const text = [WAIT_WORD[w.kind], what, secs].filter(Boolean).join(" · ");
  return (
    <div className="rlm-waits mono" data-testid="roles-live-waits" data-wait={w.kind} title={`waits on ${text}`}>
      <span className="rlm-waits-k">WAITS</span>
      <span className="rlm-waits-v">{text}</span>
    </div>
  );
}
