// Blocks you can start from (3.3.16.3): the shipped block templates (halo_harness/templates/blocks/, GET
// workflows/templates) -- each a square or a tier whose agents sit on `auto` models -- read once for the library; and
// the words the library, the confirm cards and the lines use for a square's default "when" (its covers).
import { api } from "../../../lib/api";
import { createStore, useStore } from "../../../lib/store";
import { wf, type Square } from "../workflows/store";

export type Template = {
  name: string; title: string; kind: "square" | "tier"; as: string; does: string; covers: string[];
  agents: { bio: string; model: string; lead?: boolean; alias?: string }[]; costs: string; path: string; problems: string[];
};

export const temps = createStore<{ list: Template[]; loaded: boolean }>({ list: [], loaded: false });
export const useTemplates = (): Template[] => useStore(temps, (s) => s.list);

export async function loadTemplates(): Promise<void> {
  if (temps.get().loaded) return;
  try {
    const got = await api.get<{ templates: Template[] }>("workflows/templates");
    temps.update(() => ({ list: (got.templates || []).filter((t) => !t.problems.length), loaded: true }));
  } catch {
    temps.update(() => ({ loaded: true }));
  }
}

const SAY: Record<string, string> = { vision: "images", plan: "a plan", review: "a review", "work-data": "work data" };
/** "needs pdf, images, audio" -- what a square answers when its line carries no rule of its own. */
export const coversLabel = (covers: string[]): string => {
  const words = covers.filter((c) => c !== "media").map((c) => SAY[c] || c);
  return words.length ? `needs ${words.join(", ")}` : "asked by name";
};

/** The label on a block's line: its rule, else its covers. */
export const whenLabel = (q: Square): string => q.when_label || coversLabel(q.covers);
export const connected = (q: Square): boolean => q.when_mode !== "off";

/** What the lineup side of a write touches: config on the auto lineup, else the lineup's file. */
export function writesBoard(): string {
  const b = wf.get().board;
  return !b?.lineup || b.lineup === "auto" ? "~/.halo/config.json (workflows.enabled)" : `lineup ${b.lineup}'s file (its workflows: list)`;
}
