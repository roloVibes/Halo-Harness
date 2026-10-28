// The palette's Local entries (3.3.5.0 R1): one "Local: <page>" per page, in
// the group named Local; running one opens Local on that page (pages.ts goto).
import type { Command } from "../../shell/commands";
import { goSection } from "../../lib/store";
import { goto, PAGES } from "./pages";
import { startLocal } from "./store";

export function localCommands(): Command[] {
  return PAGES.map((p) => ({
    id: "local-" + p.id,
    group: "Local",
    label: `Local: ${p.title}`,
    hint: p.built ? "the page" : `framed for 3.3.5.0 ${p.round}`,
    run: () => {
      startLocal();
      goSection("local");
      goto(p.id);
    },
  }));
}
