// Stepping in from where he sees the work (3.6.0.2 R18, the owner's point 18): a click on a box, a step row or a line of a
// run's drawing opens this card in the drawing's fixed corner for the agent doing that work (stepInTarget.ts, from the
// rows at the click): its words, then a row per live agent with Pause / Resume and Stop (routes/fleet/actions.ts, Stop
// through the fleet's confirm, re-checked there by its full key), and the steer field (routes/fleet/Steer.tsx) aimed at
// the row chosen (the first). An agent that has ended reads "ended at {t}" and offers nothing to press; a done or next
// row or a calm line has no row at all (the state only). An off-map line adds "Open the map at {sender}"; every card has
// [Open in Agents -> Live] (`onLive`: the drawing's own door). Fixed size, fixed button widths: nothing moves when a word
// changes (R12). Escape, its x or a second click on the same thing closes it. Shared with Agents' Live view: no Session
// import.
import { useEffect, useRef, useState } from "react";
import { goSection } from "../../../lib/store";
import { Button } from "../../../lib/ui";
import { setAgentsView } from "../../agents/store";
import { askStop, togglePause } from "../../fleet/actions";
import { Steer } from "../../fleet/Steer";
import { findAgent, isLive, useFleet } from "../../fleet/store";
import { STATE_WORDS } from "./LitBits";
import { openMap, setHover } from "./mapStore";
import { stateOf, type OvRow } from "./overlay";
import type { Target, Who } from "./stepInTarget";
import { StepInAsks } from "./StepInAsk";
import { agentRow, endedAt, openInAgents, openMapAt } from "./truth";

/** Agents -> Map on `map`, the sender's box marked (R18's off-map link). */
function openMapOn(map: string, sender: string): void {
  setAgentsView("map");
  goSection("agents", "map");
  void openMap(map).then(() => setHover(sender));
}

function WhoRow({ w, chosen, choose }: { w: Who; chosen: boolean; choose: () => void }) {
  const a = useFleet((s) => findAgent(s, w.key)?.a);
  const doneAt = useFleet((s) => s.doneAt[w.key]);
  const seen = useRef(0);
  const live = !!a && isLive(a);
  if (live) seen.current = 0;
  else if (!seen.current) seen.current = doneAt ? doneAt / 1000 : Date.now() / 1000; // when the card saw it end
  const paused = a?.state === "paused";
  const words = a ? agentRow(w.name, String(a.model || ""), STATE_WORDS[stateOf([a as unknown as OvRow])]).replace(" ·  · ", " · ") : w.name;
  return (
    <div className="mp-step-in-row" data-testid="map-step-in-row" data-key={w.key} data-chosen={chosen || undefined}>
      <button type="button" className="mp-step-in-who mono" data-testid="map-step-in-row-text" onClick={choose}
              title="Steer this one in the field below">{words}</button>
      {live ? (
        <span className="mp-step-in-acts">
          <Button size="sm" data-testid="map-step-in-pause" onClick={() => void togglePause(w.key)}>{paused ? "Resume" : "Pause"}</Button>
          <Button size="sm" variant="danger" data-testid="map-step-in-stop" onClick={() => askStop(w.key, "card")}>Stop</Button>
        </span>
      ) : <span className="mp-step-in-ended mono" data-testid="map-step-in-ended">{endedAt(seen.current)}</span>}
    </div>
  );
}

export function StepIn({ t, map, close, onLive }: { t: Target; map: string; close: () => void; onLive: () => void }) {
  const [pick, setPick] = useState(t.who[0]?.key || "");
  useEffect(() => setPick(t.who[0]?.key || ""), [t]);
  useEffect(() => {
    const esc = (e: KeyboardEvent) => {
      if (e.key === "Escape" && !(e.target as Element | null)?.closest?.("textarea, input")) close();
    };
    window.addEventListener("keydown", esc);
    return () => window.removeEventListener("keydown", esc);
  }, [close]);
  const steerLive = useFleet((s) => { const r = pick ? findAgent(s, pick) : null; return !!r && isLive(r.a); });
  const live = openInAgents();
  return (
    <div className="mp-step-in" data-testid="map-step-in" role="dialog" aria-label={t.title} data-target={t.id}>
      <div className="mp-step-in-head">
        <b className="mp-step-in-title" data-testid="map-step-in-title">{t.title}</b>
        <button type="button" className="mp-step-in-x" data-testid="map-step-in-close" aria-label="Close" onClick={close}>×</button>
      </div>
      <p className="mp-step-in-state mono" data-testid="map-step-in-state">{t.text}</p>
      {t.why && <p className="mp-step-in-state mono" data-testid="map-step-in-why">{t.why}</p>}
      <StepInAsks who={t.who} />
      {t.who.map((w) => <WhoRow key={w.key} w={w} chosen={w.key === pick} choose={() => setPick(w.key)} />)}
      {pick && (
        <div className="mp-step-in-steer" data-steer-key={pick}>
          <Steer k={pick} where="agent" disabled={!steerLive} />
        </div>
      )}
      <div className="mp-step-in-foot">
        {t.sender && <button type="button" className="mp-link" data-testid="map-step-in-map" onClick={() => openMapOn(map, t.sender)}>{openMapAt(t.sender)}</button>}
        <button type="button" className="mp-link" data-testid="map-step-in-live" onClick={onLive}>{live.label}</button>
      </div>
    </div>
  );
}
