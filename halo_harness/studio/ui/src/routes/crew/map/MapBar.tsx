// The Map's bar (3.6.0.0 R3, the design's "More than one map" and "Lock"): the switcher at the top left -- your maps,
// this project's first ("this project's"), the starters, "+ New map" -- with ONE switch, My sessions use this (config
// crew.map), and Lock (off by default: nothing can be dragged or changed). Under it the map's top line (what a change
// does and when it takes effect, its problem lines) and the receipt of the last change with Undo.
import { useState } from "react";
import { openGoalHere } from "../run/goalStore";
import { openFeed } from "./feedOpen";
import { Button } from "../../../lib/ui";
import { dismissError, newMap, openMap, setUse, toggleLock, undoLast, useMap } from "./mapStore";
import { Extras, LitLine, ReplayLast } from "./LitLine";
import { useLitNow } from "./useLit";

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
  const [making, setMaking] = useState(false);
  const [draft, setDraft] = useState("");
  const sorted = [...rows].sort((a, b) => (a.scope === "project" ? -1 : 0) - (b.scope === "project" ? -1 : 0));
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
      <select className="input" value={name} data-testid="map-switcher" aria-label="Which map"
              onChange={(e) => (e.target.value === "+" ? (setDraft(""), setMaking(true)) : void openMap(e.target.value))}>
        {sorted.map((r) => (
          <option key={r.name} value={r.name}>{r.name}{r.scope === "project" ? " (this project's)" : r.scope === "starter" ? " (starter)" : ""}{r.in_use ? " · my sessions use this" : ""}</option>
        ))}
        <option value="+">+ New map</option>
      </select>
    </label>
  );
}

/** The map's top line: lit (LitLine.tsx) while a session runs or a replay plays, else R3's words; R4: a box that just landed
 *  under "Not connected yet" (`fresh`) is said with a link that brings the strip into view (it can sit under the fold). */
export function TopLine({ fresh = 0 }: { fresh?: number }) {
  const locked = useMap((s) => s.locked);
  const scope = useMap((s) => s.detail?.scope);
  const L = useLitNow();
  const strip = fresh > 0 && (
    <button type="button" className="mp-link mp-fresh" data-testid="map-fresh" onClick={() => document.querySelector("[data-testid=map-strip]")?.scrollIntoView({ block: "nearest" })}>
      {fresh} new, not connected yet
    </button>
  );
  if (L.mode !== "off" || L.all.length) return <span className="mp-topwrap">{strip}<LitLine /></span>;
  return (
    <p className="cw-line mp-topline" data-testid="map-topline">
      Nothing is running on it now.<ReplayLast /> {locked ? "Locked: nothing can be moved or changed." : `Changes save at once${scope === "starter" ? " (a starter: your first change saves it as yours)" : ""}; a running session takes a line, a When or a box at its next hand-off.`}
      {strip && <> {strip}</>} <Extras L={L} />
    </p>
  );
}

export function MapBar() {
  const locked = useMap((s) => s.locked);
  const name = useMap((s) => s.name);
  const inUse = useMap((s) => s.inUse);
  const problems = useMap((s) => s.detail?.problems) || NONE;
  const receipt = useMap((s) => s.receipt);
  const error = useMap((s) => s.error);
  return (
    <div className="mp-top" data-testid="map-bar">
      <div className="mp-bar">
        <Picker />
        <Switch on={!!name && inUse === name} label="My sessions use this" testid="map-uses" onFlip={() => void setUse(inUse !== name)}
                title="New sessions run on this map (config crew.map); a running session keeps the one it started with" />
        <span className="spacer" />
        <Button size="sm" onClick={() => (openGoalHere(), openFeed("goal"))} data-testid="map-run-goal"
                title="Run a goal: several agents, one goal, one set of files -- the goal form opens in the drawer">Run a goal</Button>
        <Switch on={locked} label="Lock" testid="map-lock" onFlip={toggleLock} title="Locked: nothing on the map can be dragged or changed" />
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
