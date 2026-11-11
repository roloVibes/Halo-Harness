// A door into Session's Conversations panel on one pair (3.3.18.0 "The living canvas" part 3: a click on a line of
// Agents -> Live opens the conversation between main and the block's agent). The panel is optional and never opens on
// its own: this opens it because a line was clicked, then the panel picks the pair.
import { createStore, goSection, studio, useStore } from "../../lib/store";
import { layoutStore, showPanel, specsFor } from "../../lib/workspace/persist";
import { pairOf } from "../shared/liveTalk";

const pick = createStore<{ pair: string; n: number }>({ pair: "", n: 0 });
export const useConvPick = () => useStore(pick, (s) => s);

function whenLaidOut(fn: () => void, tries = 60): void {
  if (layoutStore("session").get().layout || tries <= 0) fn();
  else window.setTimeout(() => whenLaidOut(fn, tries - 1), 50);
}

/** Session, the Conversations panel open on the pair of `from` and `to` (agent keys). */
export function openConversation(fromKey: string, toKey: string): void {
  pick.update((s) => ({ pair: pairOf({ fromKey, toKey, machine: "" }), n: s.n + 1 }));
  if (studio.get().section !== "session") goSection("session");
  whenLaidOut(() => {
    const spec = specsFor("session")?.find((x) => x.id === "session-conversations");
    if (spec) showPanel("session", spec);
  });
}
