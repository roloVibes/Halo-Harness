// The two right drawers of Agents (3.6.0.2 R57). The Feed -- what the agents say and do, line by line -- is 4 · Live's
// drawer, keyed to Live's session: a door to it (an agent's "open", a helper's "+n under it", a wait, the plan) lands on
// Live with the Feed filtered to it and opened. 3 · Map keeps its own drawer for Run a goal and a goal run's pages
// (R42: those buttons still change the page); its title follows the page it shows. Nothing
// opens by itself.
import { createStore, goSection, useStore } from "../../../lib/store";
import { patchPanel } from "../../../lib/workspace/persist";
import { setFeedFor } from "./litStore";

export const MAP_SECTION = "agents-map";
export const LIVE_SECTION = "agents-live";
export const FEED_PANEL = "live-feed";
export const MAP_DRAWER = "map-drawer";

/** The Feed on 4 · Live, filtered to `filter` (a box, `agent:<id>`, `under:<id>`, `plan`; "" = everyone), opened. */
export function openFeed(filter: string): void {
  setFeedFor(filter);
  goSection("agents", "live");
  patchPanel(LIVE_SECTION, FEED_PANEL, { collapsed: false }, false); // kept until Live lays out (lib/workspace/kept.ts)
}

/** The Map drawer's page: `goal` (Run a goal's form, the first page), `run:<id>` (a goal run's pages)
 *  or `report:<id>` (a finished goal run's report, 3.6.0.3 B). */
const mapDrawer = createStore<{ page: string }>({ page: "goal" });
export const useMapPage = (): string => useStore(mapDrawer, (s) => s.page);
export const mapPage = (): string => mapDrawer.get().page;
/** Its title (drawerTitle.ts). */
export { mapPageTitle } from "./drawerTitle";

export function openMapDrawer(page: string): void {
  mapDrawer.update(() => ({ page }));
  patchPanel(MAP_SECTION, MAP_DRAWER, { collapsed: false }, false); // kept until the Map lays out
}

/** The Map's drawer closed (a page's own way out: the report's Back when no page sent him there). */
export function closeMapDrawer(): void {
  patchPanel(MAP_SECTION, MAP_DRAWER, { collapsed: true }, false);
}
