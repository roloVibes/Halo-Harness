// The Inspector's Assignment tab (3.0.7.0 R2): the selected card's slot in the lineup -- the bio behind it, its role,
// alias, instances, the words that route a task to it, a model override -- what resolves for it, its own problems,
// and Edit bio (the Bios panel opens on it), Duplicate and Remove (asks first). 3.1.1.0 R3: each field's help line is
// field_help.py's (lib/fieldHelp.ts). 3.3.15.0 R3: the fields' one-line hints sit in the page's `?` (TabHelp.tsx).
// 3.3.16.0 R1b "one thing at a time": a card opens on its summary (CardSummary.tsx) and Edit opens one page, its Slot
// or its Model override; with no card selected the tab shows the lineup's summary (LineupTab.tsx LineupBody) under one
// line on how to pick a card.
import { focusPanel, patchPanel } from "../../lib/workspace/persist";
import { useHelpGroup } from "../../lib/fieldHelp";
import { edit } from "./actions";
import { openBio } from "./bioActions";
import { CardSummary } from "./CardSummary";
import { ListIn, NumberIn, Pick, TextIn } from "./controls";
import { ModelSelect } from "../shared/ModelSelect";
import { setSlotModel } from "./modelActions";
import { SaveProblems } from "./LineupHeader";
import { PageFrame } from "./LineupPage";
import { LineupBody } from "./LineupTab";
import { useCardPage } from "./pages";
import { agentsOf, nodeById, useRoles } from "./store";
import type { Entry, GraphNode, Raw } from "./types";

const ROLE_NAMES = ["main", "subagent", "reviewer", "researcher", "judge", "custom"];

export function showBio(name: string): void {
  void openBio(name);
  patchPanel("roles", "roles-bios", { collapsed: false, face: "detail" }, false);
  focusPanel("roles", "roles-bios");
}

/** The card's slot page or its model page. */
function CardPage({ n, entry, page }: { n: GraphNode; entry: Entry; page: string }) {
  const bios = useRoles((s) => s.bios);
  const h = useHelpGroup("assignment");
  const set = (key: string, v: unknown) =>
    edit((r) => {
      const e = agentsOf(r)[n.index];
      if (!e) return;
      if (v === undefined || v === "" || (Array.isArray(v) && !v.length)) delete e[key];
      else e[key] = v;
    });
  const over = (entry.models && typeof entry.models === "object" ? entry.models : {}) as Raw;
  if (page === "model") {
    const own = n.bio_model ?? bios.find((b) => b.name === n.agent)?.model ?? "";
    return (
      <PageFrame id="model" title="Model override" helpId="roles-assign-help" set={!!over.preference} help={[["Model override", h.models]]}
                 what="a model for this card only; the bio and the other cards keep theirs" dflt={`the card runs on its bio's own model${own ? ` (${own})` : ""}`}>
        <ModelSelect label="Model override" value={String(over.preference || "")} testid="roles-assign-model"
                     inherit={{ label: "the bio's own", model: own }} onPick={(v) => void setSlotModel(n.index, v)} />
      </PageFrame>
    );
  }
  return (
    <PageFrame id="slot" title="Slot" helpId="roles-assign-help" set
               help={[["Agent bio", h.agent], ["Role", h.role], ["Alias (as)", h.as], ["Instances", h.instances], ["Use for", h.use_for]]}
               what="which bio fills this card, the job it does, the name the lineup calls it by, how many copies run, and the words that route a task here">
      <div className="re-form">
        <Pick label="Agent bio" value={String(entry.agent || "")} options={bios.map((b) => b.name)} onChange={(v) => set("agent", v)} hint={h.agent} testid="roles-assign-agent" />
        <Pick label="Role" value={String(entry.role || "subagent")} options={ROLE_NAMES} onChange={(v) => set("role", v)} hint={h.role} testid="roles-assign-role" />
        <TextIn label="Alias (as)" value={String(entry.as || "")} placeholder="worker, review, boss" onCommit={(v) => set("as", v.trim())} hint={h.as} testid="roles-assign-alias" />
        <NumberIn label="Instances" hint={h.instances} testid="roles-assign-instances" value={typeof entry.instances === "number" ? entry.instances : undefined}
                  onCommit={(v) => set("instances", v && v > 1 ? Math.round(v) : undefined)} />
        <ListIn label="Use for" hint={h.use_for} testid="roles-assign-use-for" value={Array.isArray(entry.use_for) ? entry.use_for : []} onCommit={(v) => set("use_for", v)} />
      </div>
    </PageFrame>
  );
}

export function Assignment() {
  const sel = useRoles((s) => s.sel);
  const n = useRoles((s) => nodeById(s, s.sel));
  const raw = useRoles((s) => s.raw);
  const page = useCardPage();
  if (!raw) return <p className="muted">Open a lineup in Lineups first.</p>;
  if (!sel || !n) {
    return (
      <div className="re-assign">
        <p className="muted ri-pick">Click a card to see its slot, or drag a bio from the Bios panel onto the canvas to add one.</p>
        <LineupBody />
      </div>
    );
  }
  const entry = (agentsOf(raw)[n.index] || {}) as Entry;
  return (
    <div className="re-assign" data-testid="roles-assignment" data-page={page || "summary"}>
      <SaveProblems />
      {page ? <CardPage n={n} entry={entry} page={page} /> : <CardSummary n={n} entry={entry} onBio={() => showBio(n.agent)} />}
    </div>
  );
}
