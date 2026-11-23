// Stepping in from where he sees the work (3.6.0.2 R18, the owner's point 18): a click on a box, a step row or a line of a
// run's drawing opens this card -- the box's sheet -- for the agent doing that work (stepInTarget.ts, from the rows at the
// click). 3.6.0.14 O1-4, it holds still, in three parts:
// - HEAD: the title and x; the state line (on a member's sheet read live from the drawing's own member, as its box reads
//   it; else the words of the click), in the rows of its longest state from the first draw; the why line; NOW of the
//   chosen row in two held rows (nowRoom.ts through sheetPlace.ts sheetHead: longer words read "a tool · {s}");
// - ONE ACTION row: Pause / Resume (76) and Stop (60) for the chosen row (routes/fleet/actions.ts, Stop through the
//   fleet's confirm), in a slot that keeps their width when it ends; "Open the map at {sender}" on an off-map line;
//   [Open in Agents -> Live] (`onLive`: the drawing's own door); under them the steer field (routes/fleet/Steer.tsx), three
//   lines at the most, scrolling inside;
// - ONE BODY, the only part that scrolls: the asks present at open, a row per live agent (a click on its words chooses it;
//   an ended one reads "ended at {t}"), main's "Told it can start: {every name}", then the asks that came later, at its end.
// - LAST SAID (O1-6, StepInSaid.tsx): what the chosen agent last said, read once at the click; the sheet opens when it is
//   read or at 1 s, and an answer that comes later goes to the body's end, "Reading what it said..." kept in its place.
// - MODEL (3.6.0.15 O2-5, StepInModel.tsx): on a member's sheet and main's only, what a model pick does for that helper;
//   read once at the click, the sheet waits for it as for Last said; answered later, it goes to the body's end.
// A calm sheet (no agent) has the state only and the link. Where it stands, how it unfolds and what folds it (Escape, its
// x, a pointer-down outside, a wheel or a zoom over the drawing; a second click on the same thing closes it): useSheet.ts.
// Shared with Agents' Live view: no Session import.
import { useEffect, useRef, useState } from "react";
import { goSection } from "../../../lib/store";
import { Button } from "../../../lib/ui";
import { setAgentsView } from "../../agents/store";
import { askStop, togglePause } from "../../fleet/actions";
import { usePanels } from "../../fleet/pstore";
import { Steer } from "../../fleet/Steer";
import { findAgent, isLive, useFleet } from "../../fleet/store";
import { pauseWord } from "../../fleet/pauseFact";
import { memberLine, memberState } from "./groupWords";
import { STATE_WORDS } from "./LitBits";
import type { Where } from "./cover";
import { focusGroup } from "./litStore";
import { openMap, setHover } from "./mapStore";
import { stateOf, type OvRow } from "./overlay";
import type { AutoGroup } from "./overlayGroups";
import { useNowOf } from "./runParts";
import { sheetHead } from "./sheetPlace";
import type { Target, Who } from "./stepInTarget";
import { askRows, StepInAsks } from "./StepInAsk";
import { saidWho, StepInSaid, useSaid } from "./StepInSaid";
import { modelAid, sheetReady } from "./modelBlock";
import { StepInModel, useModel } from "./StepInModel";
import { agentRow, endedAt, openInAgents, openMapAt } from "./truth";
import { saidParts, type Said } from "./truthBits";
import { toldEvery, type Told } from "./turnWords";
import { useSheet } from "./useSheet";

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
  const words = a ? agentRow(w.name, String(a.model || ""), STATE_WORDS[stateOf([a as unknown as OvRow])]).replace(" ·  · ", " · ") : w.name;
  return (
    <div className="mp-step-in-row" data-testid="map-step-in-row" data-key={w.key} data-chosen={chosen || undefined}>
      <button type="button" className="mp-step-in-who mono" data-testid="map-step-in-row-text" onClick={choose}
              title="Pause, stop or steer this one with the buttons and the field above">{words}</button>
      {!live && <span className="mp-step-in-ended mono" data-testid="map-step-in-ended">{endedAt(seen.current)}</span>}
    </div>
  );
}

type Props = { t: Target; where: Where; map: string; sid: string; close: () => void; onLive: () => void;
  /** what main was told it can start (main's sheet) */ told?: Told; /** the drawing's groups on Auto */ groups?: AutoGroup[] };

/** `sid`: the session drawn (3.6.0.5 B27: a group card's Open in Agents -> Live stores its group for that session first).
 *  One sheet per target: the drawings key it by `t.id`, so another box's sheet is a new one. */
export function StepIn({ t, where, map, sid, close, onLive, told, groups }: Props) {
  const [pick, setPick] = useState(t.who[0]?.key || "");
  useEffect(() => setPick(t.who[0]?.key || ""), [t]);
  const said = useSaid(sid, saidWho(t));
  const model = useModel(sid, modelAid(t.id)); // a member's and main's sheet only (ruling F): none on a group's
  const sheet = useSheet(where, t, sheetReady(said.ready, model.ready), close);
  const attn = usePanels((s) => s.attention);
  const seen = useRef<{ id: string; ids: Set<string> } | null>(null); // the asks present at open: later ones go to the end
  if (!seen.current || seen.current.id !== t.id) seen.current = { id: t.id, ids: new Set(attn.map((r) => r.id)) };
  const a = useFleet((s) => (pick ? findAgent(s, pick)?.a : undefined));
  const steerLive = !!a && isLive(a);
  const own = t.id.startsWith("member:") ? t.id.slice("member:".length) : "";
  const chosen = t.who.find((w) => w.key === pick);
  const m = groups?.flatMap((g) => g.members).find((x) => x.aid === (own || chosen?.aid));
  const state = own && m ? [memberLine(m), memberState(m)].join(" · ") : t.text;
  const nw = useNowOf(m ? m.aid : chosen?.aid || "", m ? m.raw : String(a?.state || ""), m ? m.started : Number(a?.since) || 0, m ? m.ended : 0);
  const head = sheet.width ? sheetHead(sheet.width, t.text, nw) : null; // its width at open: the head's rows are held from it
  const atOpen = useRef<Said | null>(null); // what Last said read when the sheet was placed
  if (sheet.place && atOpen.current === null) atOpen.current = said.got;
  const modelAt = useRef<boolean | null>(null); // the model's answer was there when the sheet was placed
  if (sheet.place && modelAt.current === null) modelAt.current = model.got !== "reading";
  const early = modelAt.current ?? model.got !== "reading";
  const block = (late: boolean) => model.got && early !== late && <StepInModel sid={sid} aid={modelAid(t.id) || ""} got={model.got} late={late} />;
  const parts = said.got ? saidParts(atOpen.current ?? said.got, said.got, sid) : { here: [], end: [] };
  const cut = useRef<number | null>(null); // the later asks drawn when a late answer came: it goes after them
  if (parts.end.length && cut.current === null) cut.current = askRows(attn, t.who, "later", seen.current.ids).length;
  const live = openInAgents();
  const toLive = () => {
    if (t.id.startsWith("group:")) focusGroup(sid, Number(t.id.slice("group:".length)));
    onLive();
  };
  const toldLine = t.id === "box:main" ? toldEvery(told) : "";
  return (
    <div ref={sheet.ref} className="mp-step-in" {...sheet.attrs} role="dialog" aria-label={t.title} data-target={t.id}>
      <div className="mp-step-in-head">
        <div className="mp-step-in-titlerow">
          <b className="mp-step-in-title" data-testid="map-step-in-title">{t.title}</b>
          <button type="button" className="mp-step-in-x" data-testid="map-step-in-close" aria-label="Close" onClick={sheet.fold}>×</button>
        </div>
        <p className="mp-step-in-state mono" data-testid="map-step-in-state" style={head ? { minHeight: head.stateRows * 17 } : undefined}>{state}</p>
        {t.why && <p className="mp-step-in-state mono" data-testid="map-step-in-why">{t.why}</p>}
        {(m || chosen) && (
          <p className="mp-step-in-state mp-step-in-now mono" data-testid="map-step-in-now" data-now={nw.kind}
             style={head ? { minHeight: head.nowRows * 17 } : undefined}>
            {head ? head.text : nw.text}{(head ? head.secs : nw.secs) && <span className="mp-clock-secs">{head ? head.secs : nw.secs}</span>}
          </p>
        )}
      </div>
      <div className="mp-step-in-actions" data-testid="map-step-in-actions" data-key={pick || undefined}>
        <div className="mp-step-in-btns">
          {t.who.length > 0 && (
            <span className="mp-step-in-acts mp-step-in-hold">
              {steerLive && <>
                <Button size="sm" data-testid="map-step-in-pause" onClick={() => void togglePause(pick)}>{pauseWord(a)}</Button>
                <Button size="sm" variant="danger" data-testid="map-step-in-stop" onClick={() => askStop(pick, "card")}>Stop</Button>
              </>}
            </span>
          )}
          {t.sender && <button type="button" className="mp-link" data-testid="map-step-in-map" onClick={() => openMapOn(map, t.sender)}>{openMapAt(t.sender)}</button>}
          <button type="button" className="mp-link" data-testid="map-step-in-live" onClick={toLive}>{live.label}</button>
        </div>
        {pick && (
          <div className="mp-step-in-steer" data-steer-key={pick}>
            <Steer k={pick} where="agent" disabled={!steerLive} maxRows={3} />
          </div>
        )}
      </div>
      <div className="mp-step-in-body" data-testid="map-step-in-body">
        {block(false)}
        <StepInAsks who={t.who} part="open" seen={seen.current.ids} />
        {t.who.map((w) => <WhoRow key={w.key} w={w} chosen={w.key === pick} choose={() => setPick(w.key)} />)}
        <StepInSaid lines={parts.here} />
        {toldLine && <p className="mp-step-in-state mono" data-testid="map-step-in-told">{toldLine}</p>}
        <StepInAsks who={t.who} part="later" seen={seen.current.ids} to={cut.current ?? undefined} />
        {cut.current !== null && <>
          <StepInSaid lines={parts.end} late />
          <StepInAsks who={t.who} part="later" seen={seen.current.ids} from={cut.current} />
        </>}
        {block(true)}
      </div>
    </div>
  );
}
