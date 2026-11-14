// Opening "What they think and say" (3.6.0.0 R4): a click on a lit box (or a helper, `agent:<id>`) filters the drawer to
// it and opens the drawer, which pushes the map (the room rules: a drawer, never a pop-up). Nothing opens by itself.
import { patchPanel } from "../../../lib/workspace/persist";
import { setFeedFor } from "./litStore";

export const MAP_SECTION = "agents-map";
export const FEED_PANEL = "map-feed";

export function openFeed(filter: string): void {
  setFeedFor(filter);
  patchPanel(MAP_SECTION, FEED_PANEL, { collapsed: false }, false);
}
