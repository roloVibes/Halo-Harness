// The lit Map's top line (3.6.0.0 R4, the design: "A session is running on this map (started 14:02), then the one
// sentence"): which session lights the map and when it started; the one sentence of what goes on (agents/live/narrate.ts,
// computed from the same rows and waits Live used -- who works, who waits on what or on you, the models, dollars so
// far); when an edit takes effect; in amber, a session that runs on ANOTHER map with "Show the running map"; a picker
// when more than one session runs; a session that did not start on a map said so; a Builder card the session parked
// ("answer it in the session"); a box that landed under "Not connected yet" with a link that brings the strip into view.
import { useMemo } from "react";
import { Button } from "../../../lib/ui";
import { goSection } from "../../../lib/store";
import { fleet } from "../../fleet/store";
import { liveNodes, type LiveNode } from "../../roles/liveModel";
import { narrate } from "../../agents/live/narrate";
import { useWaits } from "../../agents/live/useWaits";
import { closeRun, useMapHist } from "./mapRuns";
import { pickSession } from "./litStore";
import { openMap, useMap } from "./mapStore";
import { useLitNow, type Lit } from "./useLit";

export const WHEN_WORDS = "Edits stay allowed: a line, a When or a new box take effect at the next hand-off; an agent's own change the next time that agent starts; main's model and instructions with the next session.";
const clock = (t: number) => (t ? new Date(t * 1000).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }) : "");

function useSentence(L: Lit): string {
  const nodes: LiveNode[] = useMemo(() => (L.rec ? liveNodes(L.rec, fleet.get(), [], "", L.now * 1000) : []), [L.rec, L.now]);
  const { waits, path } = useWaits(nodes, L.now * 1000, L.mode === "live" && !L.other);
  const box = useMemo(() => {
    const m = new Map<string, string>();
    for (const [id, b] of Object.entries(L.ov?.boxes || {})) for (const a of b.agents) m.set(a, id === "main" ? "" : id);
    for (const h of L.ov?.helpers || []) m.set(h.aid, `${h.box === "main" ? "main" : h.box}'s helpers`);
    return m;
  }, [L.ov]);
  return narrate(nodes, waits, path, (n) => box.get(n.id) || "").text;
}

function Picker({ L }: { L: Lit }) {
  if (L.all.length < 2) return null;
  return (
    <select className="input mp-lit-pick" value={L.session?.sid || ""} onChange={(e) => pickSession(e.target.value)} data-testid="map-lit-pick" aria-label="Which running session lights the map">
      {L.all.map((s) => <option key={s.sid} value={s.sid}>{s.title.slice(0, 40)} ({s.map ? `map ${s.map}` : "not on a map"})</option>)}
    </select>
  );
}

export function LitLine() {
  const L = useLitNow();
  const shown = useMap((s) => s.name);
  const card = L.card.some((c) => c.target === `map:${shown}`);
  const sentence = useSentence(L);
  const run = useMapHist((s) => s.open);
  if (L.mode === "replay")
    return (
      <p className="cw-line mp-topline" data-testid="map-topline" data-lit="replay">
        Replaying {run?.title ? `"${run.title.slice(0, 60)}"` : "a past session"} {run?.map ? (run.map === shown ? "on this map" : `(it ran on ${run.map})`) : "(it did not start on a map)"}, in quiet colours.{" "}
        <Button size="sm" onClick={closeRun} data-testid="map-replay-close">Back to now</Button>
      </p>
    );
  if (!L.session) {
    const off = L.all[0];
    return (
      <p className="cw-line mp-topline" data-testid="map-topline">
        Nothing is running on it now.{off ? <> {L.all.length} session{L.all.length === 1 ? "" : "s"} running, not on a map: <Button size="sm" onClick={() => pickSession(off.sid)} data-testid="map-lit-show-nomap">Show it</Button></> : ""} {WHEN_WORDS}
      </p>
    );
  }
  const s = L.session;
  if (L.other)
    return (
      <p className="cw-line mp-topline mp-amber" data-testid="map-topline" data-lit="other">
        A session is running on another map, {s.map} (started {clock(s.started)}); this one is not lit.{" "}
        <Button size="sm" onClick={() => void openMap(s.map || "")} data-testid="map-show-running">Show the running map</Button> <Picker L={L} />
      </p>
    );
  return (
    <div className="mp-topline mp-lit-line" data-testid="map-topline" data-lit={L.nomap ? "nomap" : "live"} data-sid={s.sid}>
      <span className="cw-line" data-testid="map-lit-head">
        {L.nomap ? `This session did not start on a map (started ${clock(s.started)}): main and the helpers it made up, no lines.` : `A session is running on this map (started ${clock(s.started)}).`}
        {L.nomap && <> <Button size="sm" onClick={() => pickSession("")} data-testid="map-lit-back">Show the map again</Button></>}
        <Picker L={L} />
      </span>
      {sentence && <span className="cw-line mono" data-testid="map-lit-sentence">{sentence}</span>}
      {!L.nomap && <span className="cw-line" data-testid="map-lit-when">{WHEN_WORDS}</span>}
      {card && (
        <span className="cw-line mp-amber" data-testid="map-lit-card">
          The session asks to change this map (drawn dashed): answer it in the session.{" "}
          <Button size="sm" onClick={() => goSection("session")} data-testid="map-lit-card-go">Go to the session</Button>
        </span>
      )}
    </div>
  );
}
