// The Map's bar (3.6.0.0 R3, the design's "More than one map" and "Lock"): the switcher at the top left -- Auto (the
// default), your maps, this project's, the ones that ship with Halo, "+ New map" (pickerRows.ts, 3.6.0.5 A8) -- each saying who runs on it now ("· running in
// {session}", F2) and whether new sessions use it ("· new sessions", F4: the API's `next`; 3.6.0.2 R24), with ONE switch,
// New sessions run on this (config crew.map; mapSwitch.ts), and Lock (off by default: nothing can be dragged or changed). Under it the map's top line (what a change
// does and when it takes effect, its problem lines) and the receipt of the last change with Undo.
import { useContext, useEffect, useLayoutEffect, useRef, useState } from "react";
import { openGoalHere } from "../run/goalStore";
import { openMapDrawer } from "./feedOpen";
import { Button } from "../../../lib/ui";
import { dismissError, newMap, openMap, toggleLock, undoLast, useMap } from "./mapStore";
import { Extras, RunRow } from "./LitLine";
import { setDrafting, setUse } from "./mapSwitch";
import { QuietCtx, useQuiet } from "./mapQuiet";
import { NoticeRow } from "./NoticeRow";
import { NEXT_NONE, newSessionsRunOn, nextMap, nextName, onMap, switchLabel } from "./truth";
import { isAuto } from "./truthWords";
import { oldWords, pickerRows, pickerValue, usesSlot } from "./pickerRows";
import { copyName, copyOld } from "./oldCopy";

const NONE: never[] = []; // a selector never builds a new array (a new one each read loops React)

function Switch({ on, label, onFlip, testid, title }: { on: boolean; label: string; onFlip: () => void; testid: string; title: string }) {
  return (
    <label className="mp-switch" title={title}>
      <button type="button" role="switch" aria-checked={on} className="cw-switch" onClick={onFlip} data-testid={testid} aria-label={label} />
      <span>{label}</span>
    </label>
  );
}

function Picker() {
  const rows = useMap((s) => s.rows);
  const name = useMap((s) => s.name);
  const scope = useMap((s) => s.scope);
  const next = useMap((s) => s.next);
  const on = useQuiet().on;
  // A5: a value `{scope}:{name}` is his old file, opened by its scope (map names hold no colon)
  const open = (v: string) => { const [sc, n] = v.includes(":") ? v.split(":", 2) : ["", v]; void openMap(n, sc); };
  const [making, setMaking] = useState(false);
  const [draft, setDraft] = useState("");
  useEffect(() => (setDrafting(making), () => setDrafting(false)), [making]); // the Map's only unsaved edit (R33)
  if (making) {
    return (
      <span className="mp-new">
        <input className="input" value={draft} placeholder="release-day" aria-label="The new map's name" data-testid="map-new-name" autoFocus
               onChange={(e) => setDraft(e.target.value)} onKeyDown={(e) => { if (e.key === "Enter") void newMap(draft).then((ok) => ok && setMaking(false)); if (e.key === "Escape") setMaking(false); }} />
        <Button variant="primary" onClick={() => void newMap(draft).then((ok) => ok && setMaking(false))} data-testid="map-new-make">Make it</Button>
        <Button onClick={() => setMaking(false)}>Cancel</Button>
      </span>
    );
  }
  return (
    <label className="mp-picker">
      <span className="cw-line">Map</span>
      <select className="input" value={pickerValue(name, scope)} data-testid="map-switcher" aria-label="Which map"
              onChange={(e) => (e.target.value === "+" ? (setDraft(""), setMaking(true)) : open(e.target.value))}>
        {pickerRows(rows, on, next).map((r, i) => <option key={`${i}:${r.value}`} value={r.value}>{r.text}</option>)}
        <option value="+">+ New map</option>
      </select>
    </label>
  );
}

const OFF_SAID = "Nothing is running on it now.";

/** The room of the top line's sentence, from the first draw (P4 batch 12): a hidden twin, outside the sentence, measures
 *  the longest the sentence can be; measured again only when the width or the words change, never because a part came
 *  or went. */
function useRoom(key: string) {
  const box = useRef<HTMLDivElement>(null), twin = useRef<HTMLDivElement>(null);
  const [room, setRoom] = useState({ h: 0 });
  const [width, setWidth] = useState(0);
  useLayoutEffect(() => {
    const el = box.current;
    if (!el || typeof ResizeObserver === "undefined") return;
    const ro = new ResizeObserver(() => setWidth(Math.round(el.clientWidth)));
    ro.observe(el);
    return () => ro.disconnect();
  }, []);
  useLayoutEffect(() => {
    const said = twin.current?.firstElementChild as HTMLElement | null;
    const h = said?.offsetHeight || 0;
    if (Math.abs(h - room.h) > 0.5) setRoom({ h });
  }, [key, width]); // eslint-disable-line react-hooks/exhaustive-deps
  return { box, twin, room };
}

/** The map's top line: the reserved notice row (R55 L1-L3, R33 L4: NoticeRow.tsx), then R3's sentence in a room as tall
 *  as its longest form, then one row of controls, each in its own place: R4's "{n} new, not connected yet" (a box that
 *  just landed under "Not connected yet": a link that brings the strip into view) and the plan, from the row's left edge
 *  (3.6.0.3 B: nothing before them); then a goal run going, on a line of its own the Map's whole width, there from
 *  the first draw (LitLine.tsx RunRow, P8 batch 3 repair: the coordinator's ruling). The row's items sit at its top,
 *  so a part that grows it moves no other. A part that is not there is not drawn: no unseen copy in
 *  the sentence (P4 batch 12); the line's height never changes with a session or a row. */
export function TopLine({ fresh = 0 }: { fresh?: number }) {
  const locked = useMap((s) => s.locked);
  const scope = useMap((s) => s.detail?.scope);
  const quiet = useContext(QuietCtx);
  const runs = ["L1", "L3"].includes(quiet.facts?.kind || ""); // a session runs on it or from it now: L1/L3 says so
  const said = locked ? "Locked: nothing can be moved or changed." : `Changes save at once${scope === "starter" ? " (a starter: your first change saves it as yours)" : ""}; a running session takes a line, a When or a box at its next hand-off.`;
  const { box, twin, room } = useRoom(said);
  return (
    <div className="mp-topwrap" data-testid="map-topline">
      <NoticeRow />
      <div className="mp-topline-room" ref={box} style={room.h ? { minHeight: room.h } : undefined}>
        <p className="cw-line mp-topline" data-testid="map-topline-said">{runs ? said : `${OFF_SAID} ${said}`}</p>
        <div className="mp-notice-twin" ref={twin} aria-hidden="true">
          <p className="cw-line mp-topline">{OFF_SAID} {said}</p>
        </div>
      </div>
      <div className="mp-topline-acts" data-testid="map-topline-acts">
        {fresh > 0 && (
          <button type="button" className="mp-link mp-fresh" data-testid="map-fresh" onClick={() => document.querySelector("[data-testid=map-strip]")?.scrollIntoView({ block: "nearest" })}>
            {fresh} new, not connected yet
          </button>
        )}
        <Extras sid={quiet.sid} />
      </div>
      <RunRow />
    </div>
  );
}

export function MapBar() {
  const locked = useMap((s) => s.locked);
  const listed = useMap((s) => s.listed);
  const name = useMap((s) => s.name);
  const next = useMap((s) => s.next);
  const nextNone = useMap((s) => s.nextNone);
  const scope = useMap((s) => s.detail?.scope || "");
  const isNext = onMap(nextMap(next), name, scope); // 3.6.0.5: Auto by any of its names; his old starter file never
  const slot = usesSlot(name, scope, next, nextNone);
  // 3.6.0.5 A11: Auto has no plan to edit -- no switch, no Lock (its room kept, hidden until a map that is not Auto is
  // open: nothing is drawn that then goes away); A5: his old file neither (it is read-only, only copied)
  const noLock = slot === "old" || isAuto(name, scope);
  const names = useMap((s) => s.rows).map((r) => r.name);
  const problems = useMap((s) => s.detail?.problems) || NONE;
  const receipt = useMap((s) => s.receipt);
  const error = useMap((s) => s.error);
  return (
    <div className="mp-top" data-testid="map-bar">
      <div className="mp-bar">
        <Picker />
        {/* on: new sessions run on this map -- by identity, none set is the default starter (truth.ts nextMap; config
            never holds the default, changes_map.config_text); the tag "· new sessions" is the set map's (F4) only */}
        {/* P4 batch 12: on the map new sessions use by default (none set) the switch could change nothing: the plain sentence;
            neither is drawn before the maps are read (which one it is is not known yet; Run a goal and Lock sit after the
            spacer, so the slot filling moves nothing) */}
        {/* P7: roles off and none set, new sessions run on NO map (`next_none`, the field the truth block reads): the
            default map says the words file's sentence for that, beside a switch (off) whose press puts new sessions on it */}
        {/* P8 repair: the slot has the bar's free room to itself (the spacer gives it up), so its words wrap whole in
            the bar's row and the open map landing moves nothing on the bar (it moved 16 px when they took three lines) */}
        {/* 3.6.0.5 A11 (moved.md Q3): on Auto no switch -- none set: the sentence; new sessions get no map: NEXT_NONE
            alone; a map of his set: nothing. A5: his old file -- its words and [Copy as my-map], nothing else
            (pickerRows.ts usesSlot decides, one pure place) */}
        <span className="mp-uses-slot">{!listed || !name ? null
          : slot === "old" ? <><span className="cw-line" data-testid="map-old-words">{oldWords(name)}</span>{" "}
              <Button size="sm" data-testid="map-old-copy" onClick={() => void copyOld(name, scope)}>Copy as {copyName(names)}</Button></>
          : slot === "none" ? <span className="cw-line mp-uses-default" data-testid="map-uses-none" title={NEXT_NONE}>{NEXT_NONE}</span>
          : slot === "default" ? <span className="cw-line mp-uses-default" data-testid="map-uses-default" title={newSessionsRunOn(nextName(null))}>{newSessionsRunOn(nextName(null))}</span>
          : slot === "switch" ? <><Switch on={!nextNone && isNext} label={switchLabel()} testid="map-uses" onFlip={() => void setUse(nextNone || !isNext)}
                    title="New sessions run on this map (config crew.map); a running session keeps the one it started with" />
            {nextNone && isNext && <span className="cw-line mp-uses-default" data-testid="map-uses-none" title={NEXT_NONE}>{NEXT_NONE}</span>}</>
          : null}</span>
        <span className="spacer" />
        <Button size="sm" onClick={() => (openGoalHere(), openMapDrawer("goal"))} data-testid="map-run-goal"
                title="Run a goal: several agents, one goal, one set of files -- the goal form opens in the drawer">Run a goal</Button>
        {noLock || !name ? <span className="mp-lock-room" aria-hidden="true"><Switch on={false} label="Lock" testid="map-lock-room" onFlip={() => undefined} title="" /></span>
          : <Switch on={locked} label="Lock" testid="map-lock" onFlip={toggleLock} title="Locked: nothing on the map can be dragged or changed" />}
      </div>
      {!!problems.length && (
        <div className="mp-problems" data-testid="map-problems">
          <b>This map has a problem, so a session on it runs as with no map:</b>
          {problems.map((p) => <span key={p} className="cw-line">{p}</span>)}
        </div>
      )}
      {error && (
        <div className="mp-error" role="status" data-testid="map-error">
          <span className="cw-line">{error}</span>
          <Button onClick={dismissError}>Dismiss</Button>
        </div>
      )}
      {receipt && (
        <div className="cw-receipt" data-testid="map-receipt">
          <span className="cw-line">{receipt.line}</span>
          <Button onClick={() => void undoLast()} data-testid="map-undo">Undo</Button>
        </div>
      )}
    </div>
  );
}
