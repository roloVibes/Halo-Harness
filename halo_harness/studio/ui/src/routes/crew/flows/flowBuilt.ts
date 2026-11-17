// Agents -> 2 · Workflows remembers what main just built (3.6.0.2 R47) and keeps the Builder's hooks of the tab (moved
// here from flowStore.ts). A workflow written by a session's Builder card (`builder_done`, applied) or by an Apply on this
// tab's builder is remembered by name (`halo.studio.flow-open`, plus the in-page `pending`); the next time the tab is
// shown (its first mount, or the view changing to it) it opens in the form once -- unless the form holds an unsaved
// edit (the form is his; the list marks the built one) or a URL's `&workflow=` names another (the URL wins). Never
// `goSection`, never a pop-up, nothing while he is on the tab: the open form never changes under him.
import { onEvent } from "../../../lib/events";
import { createStore, studio, useStore, writeLocal } from "../../../lib/store";
import { agents } from "../../agents/store";
import { builders, onTab } from "../builderStore";
import { loadCrew } from "../store";
import { showFlowTry } from "./flowRun";
import { flowDirty, flows, loadFlows, openFlow, refreshCost } from "./flowStore";

export const FLOW_OPEN = "halo.studio.flow-open";
const stored = (): string => {
  try {
    return localStorage.getItem(FLOW_OPEN) || "";
  } catch {
    return "";
  }
};

/** `pending`: opens on the next showing of the tab; `built`: the list marks it until it is open in the form. */
export const flowBuilt = createStore<{ pending: string; built: string }>({ pending: stored(), built: stored() });
export const useFlowBuilt = <T,>(pick: (s: { pending: string; built: string }) => T): T => useStore(flowBuilt, pick);

export function rememberFlow(name: string): void {
  if (!name) return;
  writeLocal(FLOW_OPEN, name);
  flowBuilt.update(() => ({ pending: name, built: name }));
}

let shown = false; // the tab has mounted in this page: a later showing is an arrival
const onScreen = () => studio.get().section === "agents" && agents.get().view === "workflows";

/** The tab's first mount, before its list is read: from now on its showing again opens what was built. */
export const markFlowsShown = (): void => void (shown = true);

/** The tab shown: the remembered workflow opens once, unless the form holds an unsaved edit or it is gone (an Undo). */
export async function takeBuilt(urlNamed = false): Promise<void> {
  const name = flowBuilt.get().pending;
  if (!name) return;
  flowBuilt.update(() => ({ pending: "" }));
  writeLocal(FLOW_OPEN, null);
  const s = flows.get();
  if (urlNamed || flowDirty(s)) return;
  if (!s.flows.some((w) => w.name === name)) return flowBuilt.update(() => ({ built: "" }));
  if (s.open?.name !== name) await openFlow(name);
}

let was = onScreen();
function arrive(): void {
  const now = onScreen();
  if (now && !was && shown) void takeBuilt();
  was = now;
}
studio.subscribe(arrive);
agents.subscribe(arrive);
flows.subscribe(() => { // the built one open in the form: the list's mark is done
  const b = flowBuilt.get().built;
  if (b && flows.get().open?.name === b) flowBuilt.update(() => ({ built: "" }));
});

/** One `builder_done` frame (P2b): the last workflow it wrote. */
onEvent("builder_done", (f) => {
  const d = (f.data || {}) as Record<string, unknown>;
  if (d.outcome !== "applied") return;
  const wrote = (Array.isArray(d.wrote) ? d.wrote : []) as { kind?: string; name?: string; removed?: boolean }[];
  const last = wrote.filter((w) => w && w.kind === "workflow" && w.name && !w.removed).pop();
  if (last) rememberFlow(String(last.name));
});

/** After the builder applied (or undid): both lists again; the open workflow from disk unless the form holds edits. An
 *  Apply's last workflow other than the one in the form is remembered (R47). */
async function after(targets: string[]): Promise<void> {
  await Promise.all([loadFlows(), loadCrew()]);
  const s = flows.get();
  const name = s.form?.name || "";
  const applied = builders.workflows.get().receipt?.touched === targets; // an Undo clears the receipt first
  const made = targets.filter((t) => t.startsWith("workflow:")).map((t) => t.slice(9)).filter((n) => n && n !== name).pop();
  if (applied && made) rememberFlow(made);
  if (!targets.includes(`workflow:${name}`)) return refreshCost();
  if (s.open?.name && flowDirty(s)) return flows.update(() => ({ stale: true }));
  if (flows.get().flows.some((w) => w.name === name)) await openFlow(name);
  else if (s.open?.name) flows.update(() => ({ open: null, form: null, saved: null }));
}

onTab("workflows", {
  selection: () => {
    const s = flows.get();
    return s.form ? { workflow: s.form.name, ...(flowDirty(s) || !s.saved ? { unsaved: s.form } : {}) } : {};
  },
  after,
  show: (rec) => showFlowTry(rec.id),
});
