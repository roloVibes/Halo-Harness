// Agents -> 3 · Map (3.6.0.0 R3, the v3 design's third tab; docs/STUDIO-map.md): connect your agents and workflows --
// main at the left, a box per agent or workflow, one kind of line ("hands work to") with its When in words. The room
// rules (R0a): the map is the main thing (the bar, the drawing, the strip under it); "Agents and workflows" is a left
// drawer that pushes the map (closed until you open it from the view bar); the builder is docked at the foot. The view
// bar carries Agents' switch and the Attention chip. Nothing opens by itself. 3.6.0.2 R57: the Feed is 4 · Live's; the
// Map's right drawer keeps Run a goal and a goal run's pages (MapDrawer.tsx), titled by the page it shows. 3.6.0.3 B:
// the Map draws the plan and what runs now, never the past. 3.6.0.5 A11: Auto has no plan to edit -- its tab draws
// AutoPlan.tsx (main alone and M1) in place of the drawing, the strip and the cards.
import { useEffect, useMemo, useLayoutEffect, useRef, useState, type RefObject, type CSSProperties } from "react";
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
import { AutoPlan } from "./AutoPlan";
import { MapBar } from "./MapBar";
import { MapCanvas } from "./MapCanvas";
import { loadMaps, mapTabGone, openFirst, useMap } from "./mapStore";
import { Strip } from "./Strip";
import { PickList, WhenCard } from "./WhenCard";
import { MAP_DRAWER, MAP_SECTION, mapPage, mapPageTitle, useMapPage } from "./feedOpen";
import { MapDrawer, MapDrawerGlance, useGoalOnOpen } from "./MapDrawer";
import { useFleet } from "../../fleet/store";
import { LitCtx, useLit } from "./useLit";
import { QuietCtx, useQuiet } from "./mapQuiet";
import { markMapDrawn } from "./mapSwitch";
import { isAuto } from "./truthWords";

export { MAP_SECTION };

function ListGlance() {
  const n = useCrew((s) => s.agents.length + s.starters.length) + useFlows((s) => s.flows.length + s.starters.length);
  return <div className="glance"><div className="glance-hint">{n} agents and workflows to put on the map. Expand for the list.</div></div>;
}

function MainGlance() {
  const name = useMap((s) => s.name);
  return <div className="glance"><div className="glance-hint">{name ? `The map ${name}: expand it.` : "Pick a map."}</div></div>;
}

/** 3.6.0.0 R5c: what the Map is drawn from has landed -- the map list and the open map (or why not), the agents, the
 *  workflows and the sessions (`data-settled`, what the tests wait on). */
function useSettled(): boolean {
  const map = useMap((s) => s.listed && (!!s.detail || !!s.error || !s.rows.length));
  const agents = useCrew((s) => s.loaded);
  const flows = useFlows((s) => s.loaded);
  const sessions = useFleet((s) => s.loaded);
  return map && agents && flows && sessions;
}

/** P4 batch 12 (the coordinator's ruling): the canvas' least height is what the Map panel's real box leaves after the
 *  bar and the strip, measured (never the window's height minus a constant), so the strip is in sight at rest; measured
 *  again when the panel or a part above or under the canvas changes size. */
function useCanvasRoom(root: RefObject<HTMLDivElement | null>): number {
  const [room, setRoom] = useState(0);
  useLayoutEffect(() => {
    const el = root.current;
    let body = el?.parentElement || null;
    while (body && !/(auto|scroll)/.test(getComputedStyle(body).overflowY)) body = body.parentElement;
    if (!el || !body || typeof ResizeObserver === "undefined") return;
    const measure = () => {
      const kids = ([...el.children] as HTMLElement[]).filter((k) => k.offsetParent !== null && getComputedStyle(k).position !== "absolute" && getComputedStyle(k).position !== "fixed");
      const others = kids.filter((k) => !k.classList.contains("mp-canvas")).reduce((n, k) => n + k.offsetHeight, 0);
      const gap = parseFloat(getComputedStyle(el).rowGap) || 0;
      const top = el.getBoundingClientRect().top - body!.getBoundingClientRect().top + body!.scrollTop;
      const h = Math.max(120, Math.floor(body!.clientHeight - top - others - gap * Math.max(0, kids.length - 1) - 2));
      setRoom((r) => (Math.abs(r - h) > 0.5 ? h : r));
    };
    // P7: set up once (a dependency array); a part coming or going above or under the canvas is seen by the
    // MutationObserver, which observes the new set of parts and measures again
    const ro = new ResizeObserver(measure);
    const watch = () => {
      ro.disconnect();
      ro.observe(body!);
      for (const k of [...el.children]) if (!k.classList.contains("mp-canvas")) ro.observe(k);
      measure();
    };
    const mo = new MutationObserver(watch);
    mo.observe(el, { childList: true });
    watch();
    return () => (ro.disconnect(), mo.disconnect());
  }, [root]);
  return room;
}

function MapMain() {
  const locked = useMap((s) => s.locked);
  const name = useMap((s) => s.name);
  const scope = useMap((s) => s.detail?.scope || "");
  const root = useRef<HTMLDivElement>(null);
  const room = useCanvasRoom(root);
  const settled = useSettled();
  const quiet = useQuiet(); // R55: the one quiet line and the marks of running workflows' boxes
  return (
    <QuietCtx.Provider value={quiet}>
    <div className="mp" ref={root} style={room ? ({ "--mp-canvas-min": `${room}px` } as CSSProperties) : undefined} data-testid="map" data-locked={locked || undefined} data-settled={settled || undefined}>
      <MapBar />
      {/* no map open yet: the drawing's room only, so nothing drawn for another map goes away when Auto lands */}
      {!name ? <div className="mp-canvas" data-testid="map-canvas" /> : isAuto(name, scope) ? <AutoPlan />
        : <><MapCanvas /><Strip /><WhenCard /><PickList /></>}
    </div>
    </QuietCtx.Provider>
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
    help: "Drag a box's dot to another box to connect them, or click the dot for a list.\nClick a line's label: its When, or take it out.\nClick a workflow box: its steps.\nNew sessions run on this: new sessions run on this map.",
    face: "detail", glance: MainGlance, detail: MapMain },
  { id: "map-builder", testid: "map-builder-panel", title: "Builder", role: "dock",
    about: "Say how things should connect, or ask why something happened: the builder answers with a preview you tick, then Apply.",
    help: "Type what you want and press Enter.\nThe changes show on the map as dashed ghosts.\nApply writes; Undo puts it back.",
    face: "detail", glance: MapBuilder, detail: MapBuilder },
  planPanel, // 3.6.0.0 R5: a goal run's plan review (crew/run/planPanel.ts), optional, opened by "Review the plan"
];

/** 3.6.0.2 R57: the Map's right drawer; its title follows its page (the words on the button that opened it). */
const mapDrawerSpec = (page: string): PanelSpec => ({
  id: MAP_DRAWER, testid: "map-drawer-panel", title: mapPageTitle(page), role: "drawer", side: "right", contentW: 420,
  about: "Run a goal's form, or a goal run's pages: while it runs, then its report.",
  help: "Run a goal (in the map's bar): the goal form opens here.\nA goal run's Open (in the map's bar): its pages open here.\nIts × closes the page and the drawer.",
  face: "detail", glance: MapDrawerGlance, detail: MapDrawer,
});
/** The Map's panels as they are now (the palette's Show panel lines, the Inspector). */
export const mapPanelsNow = (): PanelSpec[] => [...mapPanels, mapDrawerSpec(mapPage())];

export function MapView() {
  const crewLoaded = useCrew((s) => s.loaded);
  const flowsLoaded = useFlows((s) => s.loaded);
  useGoalOnOpen(); // 3.6.0.3 B: his opening of the drawer on Run a goal's page opens the form (MapDrawer.tsx)
  useEffect(() => {
    markMapDrawn(); // 3.6.0.2 R33: a map built from now on waits for him (mapSwitch.ts)
    void loadMaps().then(openFirst); // k/batch02 entry 2: a map asked by scope from another section, else firstName()
    if (!crewLoaded) void loadCrew();
    if (!flowsLoaded) void loadFlows();
    return mapTabGone;
  }, []); // eslint-disable-line react-hooks/exhaustive-deps
  const lead = (
    <span className="cw-lead">
      <ViewSwitch view="map" />
      <AttentionChip />
    </span>
  );
  const lit = useLit(); // R55, 3.6.0.3 B Z8: always off (the Map is the plan); its running sessions for the quiet line
  const reg = usePacks((s) => s.reg);
  // 3.6.0.0 R5: a pack's panel declared for Agents (or its old words: roles, orchestra, team) joins the Map's workspace,
  // where Cast's workspace held it before
  const page = useMapPage();
  const specs = useMemo(() => [...mapPanels, mapDrawerSpec(page), ...PACK_WORDS.flatMap((w) => packPanels(reg, w))], [reg, page]);
  return (
    <LitCtx.Provider value={lit}>
      <div className="cw" data-testid="map-view">
        <Workspace section={MAP_SECTION} specs={specs} lead={lead} />
      </div>
    </LitCtx.Provider>
  );
}
