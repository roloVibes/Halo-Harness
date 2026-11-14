// Agents -> 3 · Map (3.6.0.0 R3, the v3 design's third tab; docs/STUDIO-map.md): connect your agents and workflows --
// main at the left, a box per agent or workflow, one kind of line ("hands work to") with its When in words. The room
// rules (R0a): the map is the main thing (the bar, the drawing, the strip under it); "Agents and workflows" is a left
// drawer that pushes the map (closed until you open it from the view bar); the builder is docked at the foot. The view
// bar carries Agents' switch and the Attention chip. Nothing opens by itself.
import { useEffect } from "react";
import { Workspace } from "../../../lib/workspace/Workspace";
import type { PanelSpec } from "../../../lib/workspace/types";
import { AttentionChip } from "../../agents/AttentionChip";
import { ViewSwitch } from "../../agents/ViewSwitch";
import { MapBuilder } from "../Builder";
import { loadCrew, useCrew } from "../store";
import { loadFlows, useFlows } from "../flows/flowStore";
import { AddList } from "./AddList";
import { MapBar } from "./MapBar";
import { MapCanvas } from "./MapCanvas";
import { firstName, loadMaps, openMap, useMap } from "./mapStore";
import { Strip } from "./Strip";
import { PickList, WhenCard } from "./WhenCard";
import { Feed } from "./Feed";
import { FEED_PANEL, MAP_SECTION } from "./feedOpen";
import { MapHistory } from "./MapHistory";
import { LitCtx, useLit, useLitNow } from "./useLit";

export { MAP_SECTION };

function ListGlance() {
  const n = useCrew((s) => s.agents.length + s.starters.length) + useFlows((s) => s.flows.length + s.starters.length);
  return <div className="glance"><div className="glance-hint">{n} agents and workflows to put on the map. Expand for the list.</div></div>;
}

function MainGlance() {
  const name = useMap((s) => s.name);
  return <div className="glance"><div className="glance-hint">{name ? `The map ${name}: expand it.` : "Pick a map."}</div></div>;
}

function FeedGlance() {
  const L = useLitNow();
  return <div className="glance"><div className="glance-hint">{L.mode === "live" ? "What the agents think and say: expand it, or click a box." : "Nothing runs on this map now."}</div></div>;
}

function MapMain() {
  const locked = useMap((s) => s.locked);
  const L = useLitNow();
  return (
    <div className="mp" data-testid="map" data-locked={locked || undefined} data-lit={L.ov ? L.mode : undefined}>
      <MapBar />
      <MapCanvas />
      <Strip />
      <MapHistory />
      <WhenCard />
      <PickList />
    </div>
  );
}

export const mapPanels: PanelSpec[] = [
  { id: "map-add", testid: "map-add-panel", title: "Agents and workflows", role: "drawer", side: "left", contentW: 360,
    about: "Your agents, then your workflows: drag one onto the map, or Add it.",
    help: "Drag a row onto a box: that box hands work to it (its When card opens).\nDrag it onto the strip, or press Add: it waits under Not connected yet.\nEnter on a row adds it.",
    face: "detail", glance: ListGlance, detail: AddList },
  { id: "map-main", testid: "map-main-panel", title: "Map", role: "main",
    about: "Who main hands work to, and when: boxes, lines, each line's When in words; the boxes nothing hands work to wait under it.",
    help: "Drag a box's dot to another box to connect them, or click the dot for a list.\nClick a line's label: its When, or take it out.\nClick a workflow box: its steps.\nMy sessions use this: new sessions run on this map.",
    face: "detail", glance: MainGlance, detail: MapMain },
  { id: FEED_PANEL, testid: "map-feed-panel", title: "What they think and say", role: "drawer", side: "right", contentW: 420,
    about: "While a session runs on this map: each agent's thoughts, words, tools, hand-offs to other agents and asks, newest at the bottom.",
    help: "Click a box on the map: only its agents (or pick everyone).\nSteer: a few words the agent reads before its next step.\nStop: it stops at its next step.\nAn ask's answers are its buttons.",
    face: "detail", glance: FeedGlance, detail: Feed },
  { id: "map-builder", testid: "map-builder-panel", title: "Builder", role: "dock",
    about: "Say how things should connect, or ask why something happened: the builder answers with a preview you tick, then Apply.",
    help: "Type what you want and press Enter.\nThe changes show on the map as dashed ghosts.\nApply writes; Undo puts it back.",
    face: "detail", glance: MapBuilder, detail: MapBuilder },
];

export function MapView() {
  const crewLoaded = useCrew((s) => s.loaded);
  const flowsLoaded = useFlows((s) => s.loaded);
  useEffect(() => {
    void loadMaps().then(() => openMap(firstName()));
    if (!crewLoaded) void loadCrew();
    if (!flowsLoaded) void loadFlows();
  }, []); // eslint-disable-line react-hooks/exhaustive-deps
  const lead = (
    <span className="cw-lead">
      <ViewSwitch view="map" />
      <AttentionChip />
    </span>
  );
  const lit = useLit(); // R4: one overlay for the whole tab (the canvas, the strip, the top line, the drawer)
  return (
    <LitCtx.Provider value={lit}>
      <div className="cw" data-testid="map-view">
        <Workspace section={MAP_SECTION} specs={mapPanels} lead={lead} />
      </div>
    </LitCtx.Provider>
  );
}
