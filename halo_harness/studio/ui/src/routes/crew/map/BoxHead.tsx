// The drawer's head for the clicked box (3.6.0.0 R4b, R4's gap 5: what Live's agent inspector and node menu gave): a
// row per fact for the box's agent -- its model and WHY it was picked (Auto's reason line), what it may use, its
// tokens, its cost, how long it has run -- and beside Steer and Stop (Feed.tsx) the owner's other controls: Pause /
// Resume (the same route Live's node menu calls, routes/fleet/actions.ts togglePause) and, on a failed agent, Dismiss
// (Live's own: agents/live/now.ts dismiss + roles/glow.ts ackFailed). "Hand to another machine" is not carried over.
// 3.6.0.0 R5 (Live's node menu went): Take over beside Pause -- your brief replaces its task, recorded as a hand-off
// (routes/fleet/extras.ts askHandoff, the same dialog and route the palette's "take over" uses).
import { Button } from "../../../lib/ui";
import type { RecordAgent } from "../../../lib/work/record";
import { togglePause } from "../../fleet/actions";
import { pauseSet } from "../../fleet/pauseFact";
import { askHandoff } from "../../fleet/extras";
import { agentCost, watchWhy } from "../../fleet/watchOnly";
import { ackFailed } from "../live/glow";
import type { LiveAgent } from "../models/types";
import { dismiss, useDismissed } from "../live/now";
import { secsWords } from "../live/waits";
import { useMap } from "./mapStore";
import { STATE_WORDS } from "./LitBits";
import type { Lit } from "./useLit";

const LIVE = ["queued", "running", "waiting", "paused"];
const count = (n: number) => (n >= 10000 ? `${Math.round(n / 1000)}k` : n >= 1000 ? `${(n / 1000).toFixed(1)}k` : String(n));

/** What the agent may use: its box's agent file (`uses`), a made-up helper main's own, else unknown. */
function useUses(a: RecordAgent): string {
  const boxes = useMap((s) => s.detail?.boxes);
  if (a.row.crew?.made_up) return "what main may use (a helper made up for this task)";
  if (a.id === "main" || !a.parent) return "the session's own tools";
  for (const b of Object.values(boxes || {})) {
    const f = b.facts.find((x) => x.name === a.name);
    if (f) return (f.uses || []).join(", ") || "nothing beyond reading its task";
  }
  return "";
}

export function BoxHead({ L, a, box }: { L: Lit; a: RecordAgent; box: string }) {
  const gone = useDismissed().includes(a.key);
  const uses = useUses(a);
  const r = a.row;
  const t0 = a.started ? a.started * 1000 : null;
  const ran = secsWords(t0, (a.ended || L.now) * 1000);
  const live = LIVE.includes(a.state);
  const tin = Number(r.tokens_in || 0), tout = Number(r.tokens_out || 0);
  const state = a.state === "paused" ? "paused" : a.state === "waiting" ? STATE_WORDS.waiting : a.state || "not started";
  const set = pauseSet({ state: a.state, pause_set: r.pause_set }); // F3: what a press of Pause / Resume does
  const watch = watchWhy(L.rec); // 3.6.0.25 G: a Claude Code session: cost not known, Pause and Take over off
  return (
    <section className="mpf-head" data-testid="map-feed-head" data-agent={a.id} data-box={box} data-state={a.state}>
      <span className="mpf-fact" data-testid="map-fact-who"><b>{a.name}</b> · {state}{box && box !== a.name ? ` · the box ${box}` : ""}</span>
      <span className="mpf-fact mono" data-testid="map-fact-model">runs on {a.model || "the session's model"}</span>
      {a.reason && <span className="mpf-fact" data-testid="map-fact-why">why this model: {a.reason}</span>}
      {uses && <span className="mpf-fact" data-testid="map-fact-uses">may use: {uses}</span>}
      {(tin > 0 || tout > 0) && <span className="mpf-fact mono" data-testid="map-fact-tokens">tokens: {count(tin)} in · {count(tout)} out</span>}
      <span className="mpf-fact mono" data-testid="map-fact-cost">cost: {agentCost(L.rec, a.cost || 0)}</span>
      {ran && <span className="mpf-fact mono" data-testid="map-fact-ran">{live ? "running for" : "ran for"} {ran}</span>}
      {(live || (a.state === "failed" && !gone)) && (
        <span className="mpf-buttons" data-testid="map-feed-more">
          {live && (
            <Button onClick={() => void togglePause(a.key)} data-testid="map-feed-pause" data-paused={set || undefined} disabled={!!watch}
                    title={watch || (set ? `Resume ${a.name}` : `Pause ${a.name}: it holds at its next tool or model call`)}>
              {set ? `Resume ${a.name}` : `Pause ${a.name}`}
            </Button>
          )}
          {live && a.id !== "main" && (
            <Button onClick={() => askHandoff("take_over", a.key)} data-testid="map-feed-takeover" disabled={!!watch}
                    title={watch || `Take over ${a.name}: your brief replaces its task, recorded as a hand-off`}>Take over</Button>
          )}
          {a.state === "failed" && !gone && (
            <Button onClick={() => (dismiss(a.key), ackFailed([{ key: a.key, state: "failed" } as LiveAgent]))} data-testid="map-feed-dismiss"
                    title={`Seen: ${a.name} failed; this hides it here`}>Dismiss</Button>
          )}
        </span>
      )}
    </section>
  );
}
