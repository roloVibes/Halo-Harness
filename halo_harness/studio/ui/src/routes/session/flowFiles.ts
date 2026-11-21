// 3.6.0.9 V batch 2 (the owner's point 34: "it's not showing any changes made when I tell the in a session to make a
// change to the workflow"): a workflow file written by a plain write (a session's Edit or Write, a hand) is said in
// Session's truth block, not only drawn: "The workflow {name} changed at {time}. A run already going keeps its steps;
// the next run takes the change." (truth.ts flowChangedLine). For each session of this harness whose drawing has a box
// running that workflow (the map the page holds, mapFiles.ts `names`), or on Auto one it has run or is running as far
// as the page knows (its rows and map_step frames), and only when no builder_done named that same write (the hash the
// card's frame gave it, built.ts `builtSigOf`: the watcher's frame for the card's own write says nothing more). The
// time is the page's clock when the change is heard. No line for an agent file. Nothing here reaches a model.
import { onFilesChanged, type FilesChange } from "../../lib/filesLive";
import { builtSigOf, flowChanged } from "../crew/map/built";
import { lit, toLit } from "../crew/map/litStore";
import { names } from "../crew/map/mapFiles";
import type { SessionRow } from "../fleet/types";
import { knownFlows } from "./statusOf";

/** One burst of workflow files written, heard with this harness's session rows `rows`. */
export function takeFlowFiles(c: FilesChange, rows: SessionRow[], now = Date.now() / 1000): void {
  for (const w of c.names) {
    const own = builtSigOf(w), k = `workflows:${w}`;
    // the Builder card's own write, heard again from the watcher: the file Studio reads, or (a session in another
    // folder writes the file it reads) the very file that moved, has the hash the card's frame gave (batch 2 repair)
    if (own && (c.sigs[k] === own || (c.moved?.[k] || []).includes(own))) continue;
    for (const r of rows) {
      const s = toLit(r);
      const boxed = !!s.map && names(s.map, "workflows", w);
      const ran = !boxed && s.auto && knownFlows(r.agents || [], lit.get().events[s.sid] || []).some((k) => k.name === w);
      if (boxed || ran) flowChanged(s.sid, w, now);
    }
  }
}

/** Hear the workflow files (once a page); `rows()` gives this harness's sessions at the time. */
export const startFlowFiles = (rows: () => SessionRow[]): (() => void) => onFilesChanged("workflows", (c) => takeFlowFiles(c, rows()));
