// Agents -> 3 · Map (3.6.0.0 R3, the v3 design's third tab; docs/STUDIO-map.md): connect your agents and workflows --
// main at the left, a box per agent or workflow, one kind of line ("hands work to") with its When in words. The room
// rules (R0a): the map is the main thing (the bar, the drawing, the strip under it); "Agents and workflows" is a left
// drawer that pushes the map (closed until you open it from the view bar); the builder is docked at the foot. The view
// bar carries Agents' switch and the Attention chip. Nothing opens by itself.
import { useEffect, useMemo } from "react";
import { Workspace } from "../../../lib/workspace/Workspace";
import type { PanelSpec } from "../../../lib/workspace/types";
import { planPanel } from "../run/planPanel";
import { packPanels } from "../../packs/registry";
import { usePacks } from "../../packs/store";
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
import { MapHistory, MapHistoryLoad } from "./MapHistory";
import { loadMapHistory, useMapHist } from "./mapRuns";
import { useFleet } from "../../fleet/store";
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

/** 3.6.0.0 R5c: what sits above History has landed -- the map list and the open map (or why not), the agents, the
 *  workflows, the sessions and History's own runs. Until then History is not drawn: drawn at once it moved 280 px down
 *  and 670 px right as they landed, out from under a click (its "Goal runs, files, Compare" on a slow machine). */
function useSettled(): boolean {
  const map = useMap((s) => s.listed && (!!s.detail || !!s.error || !s.rows.length));
  const agents = useCrew((s) => s.loaded);
  const flows = useFlows((s) => s.loaded);
  const sessions = useFleet((s) => s.loaded);
  const runs = useMapHist((s) => s.loaded);
  return map && agents && flows && sessions && runs;
}

function MapMain() {
  const locked = useMap((s) => s.locked);
  const L = useLitNow();
  const settled = useSettled();
  const runningKey = L.all.map((s) => s.sid).join(",");
  useEffect(() => void loadMapHistory(new Set(runningKey ? runningKey.split(",") : [])), [runningKey]); // History's runs (MapHistory.tsx)
  return (
    <div className="mp" data-testid="map" data-locked={locked || undefined} data-lit={L.ov ? L.mode : undefined} data-settled={settled || undefined}>
      <MapBar />
      <MapCanvas />
      <Strip />
      {settled ? <MapHistory /> : <MapHistoryLoad />}
      <WhenCard />
      <PickList />
    </div>
  );
}

const PACK_WORDS = ["agents", "roles", "orchestra", "team"];

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
  planPanel, // 3.6.0.0 R5: a goal run's plan review (crew/run/planPanel.ts), optional, opened by "Review the plan"
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
  const reg = usePacks((s) => s.reg);
  // 3.6.0.0 R5: a pack's panel declared for Agents (or its old words: roles, orchestra, team) joins the Map's workspace,
  // where Cast's workspace held it before
  const specs = useMemo(() => [...mapPanels, ...PACK_WORDS.flatMap((w) => packPanels(reg, w))], [reg]);
  return (
    <LitCtx.Provider value={lit}>
      <div className="cw" data-testid="map-view">
        <Workspace section={MAP_SECTION} specs={specs} lead={lead} />
      </div>
    </LitCtx.Provider>
  );
}
