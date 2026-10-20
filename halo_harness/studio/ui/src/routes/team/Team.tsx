// Team (Alt+2, 3.0.8.0 R2): the project's team file as one board. Until the
// team loads clean the section is the Start view (Start.tsx); then three
// panels: the Board (team-board: the run bar, members as columns, stages as
// boxes, blocks in the band underneath, the trigger, read and write edges),
// the Inspector (team-inspector: the selected stage with Run and its gate
// card, block with holders and changes, or member) and the change feed
// (team-feed: the run's event lines with the kind chips). One store
// (store.ts) fed by sync.ts from the Team routes and the `team` frames.
// Layout at 1440x900: the board 0,0 w18 h78 (a small team's whole board, no
// scroll), the Inspector the whole right column (18,0 w6, full height: the
// gate card and the change list are long), the feed under the board (0,78
// w18, the rest of the height).
import { useEffect } from "react";
import type { MotionState } from "../../lib/motion";
import type { PanelSpec } from "../../lib/workspace/types";
import { HELP } from "../help";
import { BoardDetail, BoardGlance, useBoardMotion } from "./Board";
import { FeedDetail, FeedGlance, useFeedMotion } from "./Feed";
import { InspectorDetail, InspectorGlance, useInspectorMotion } from "./Inspector";
import { startTeam } from "./sync";

function started(hook: () => MotionState): () => MotionState {
  return () => {
    useEffect(() => startTeam(), []);
    return hook();
  };
}

const panel = (id: string, rest: Omit<PanelSpec, "id" | "testid">): PanelSpec => ({ id, testid: id, ...HELP[id], ...rest });

export const teamPanels: PanelSpec[] = [
  panel("team-board", { title: "Board", x: 0, y: 0, w: 18, h: 78, minW: 8, minH: 24, face: "detail", glance: BoardGlance, detail: BoardDetail, useMotion: started(useBoardMotion) }),
  panel("team-inspector", { title: "Inspector", x: 18, y: 0, w: 6, h: 0, minW: 4, minH: 16, face: "detail", glance: InspectorGlance, detail: InspectorDetail, useMotion: started(useInspectorMotion) }),
  panel("team-feed", { title: "Change feed", x: 0, y: 78, w: 18, h: 0, minW: 6, minH: 10, face: "detail", glance: FeedGlance, detail: FeedDetail, useMotion: started(useFeedMotion) }),
];
