// The Inspector's Assignment tab (3.0.7.0 R2): the selected card's slot in
// the lineup -- the bio behind it, its role, alias, instances, the words that
// route a task to it, which card it reports to, a model override -- what
// resolves for it (model, fallback, price, context, tier), its own problems,
// and Edit bio (the Bios panel opens on it), Duplicate and Remove (asks
// first). With no card selected: the lineup's description and about.
// 3.1.1.0 R3: each field's help line is field_help.py's (lib/fieldHelp.ts).
import { focusPanel, patchPanel } from "../../lib/workspace/persist";
import { useHelpGroup } from "../../lib/fieldHelp";
import { Button } from "../../lib/ui";
import { edit, setReportsTo } from "./actions";
import { openBio } from "./bioActions";
import { ListIn, NumberIn, Pick, TextIn } from "./controls";
import { LineupHeader, SaveProblems } from "./LineupTab";
import { agentsOf, keyOf, modelRow, nodeById, openDialog, priceText, useRoles } from "./store";
import type { Entry, Raw } from "./types";

const ROLE_NAMES = ["main", "subagent", "reviewer", "researcher", "judge", "custom"];

export function showBio(name: string): void {
  void openBio(name);
  patchPanel("roles", "roles-bios", { collapsed: false, face: "detail" }, false);
  focusPanel("roles", "roles-bios");
}

function reportsOf(raw: Raw | null, title: string): string {
  const org = raw?.org as { positions?: Raw[] } | undefined;
  const pos = (org?.positions || []).find((p) => p && p.title === title);
  return pos && typeof pos.reports_to === "string" ? pos.reports_to : "";
}

export function Assignment() {
  const sel = useRoles((s) => s.sel);
  const n = useRoles((s) => nodeById(s, s.sel));
  const raw = useRoles((s) => s.raw);
  const bios = useRoles((s) => s.bios);
  const tier = useRoles((s) => s.graph?.tiers.find((t) => t.node_ids.includes(s.sel)));
  const model = useRoles((s) => (n ? modelRow(s, n.model) : undefined));
  const models = useRoles((s) => s.models);
  const h = useHelpGroup("assignment");
  if (!raw) return <p className="muted">Open a lineup in Lineups first.</p>;
  if (!sel || !n) {
    return (
      <div className="re-assign">
        <SaveProblems />
        <p className="muted">Click a card to edit its slot, or drag a bio from the Bios panel onto the canvas to add one.</p>
        <LineupHeader />
      </div>
    );
  }
  const entry = (agentsOf(raw)[n.index] || {}) as Entry;
  const set = (key: string, v: unknown) =>
    edit((r) => {
      const e = agentsOf(r)[n.index];
      if (!e) return;
      if (v === undefined || v === "" || (Array.isArray(v) && !v.length)) delete e[key];
      else e[key] = v;
    });
  const title = keyOf(n);
  const main = agentsOf(raw).find((e) => e.role === "main") as Entry | undefined;
  const others = agentsOf(raw).filter((_e, i) => i !== n.index).map((e) => String(e.as || e.role || "")).filter(Boolean);
  const over = (entry.models && typeof entry.models === "object" ? entry.models : {}) as Raw;
  return (
    <div className="re-assign" data-testid="roles-assignment">
      <SaveProblems />
      <header className="re-assign-head">
        <b>{n.agent}</b>
        <span className="mono muted">{title}{tier ? ` · tier ${tier.index} (${tier.name})` : ""}</span>
      </header>
      <Pick label="Agent bio" value={String(entry.agent || "")} options={bios.map((b) => b.name)} onChange={(v) => set("agent", v)} hint={h.agent} testid="roles-assign-agent" />
      <Pick label="Role" value={String(entry.role || "subagent")} options={ROLE_NAMES} onChange={(v) => set("role", v)} hint={h.role} testid="roles-assign-role" />
      <TextIn label="Alias (as)" value={String(entry.as || "")} placeholder="worker, review, boss" onCommit={(v) => set("as", v.trim())} hint={h.as} testid="roles-assign-alias" />
      <NumberIn label="Instances" hint={h.instances} testid="roles-assign-instances" value={typeof entry.instances === "number" ? entry.instances : undefined} onCommit={(v) => set("instances", v && v > 1 ? Math.round(v) : undefined)} />
      <ListIn label="Use for" hint={h.use_for} testid="roles-assign-use-for" value={Array.isArray(entry.use_for) ? entry.use_for : []} onCommit={(v) => set("use_for", v)} />
      {entry.role !== "main" && (
        <Pick label="Reports to" value={reportsOf(raw, title)} options={["", ...others.filter((t) => t !== (main?.as || main?.role))]}
              labels={{ "": "the main card (the starting box)" }} onChange={(v) => setReportsTo(n.index, v)} hint="you can also drop the card onto another card" />
      )}
      <Pick label="Model override" hint={h.models} value={String(over.preference || "")} options={["", ...models.map((m) => m.ref)]}
            onChange={(v) => set("models", v ? { ...over, preference: v } : Object.keys(over).filter((k) => k !== "preference").length ? Object.fromEntries(Object.entries(over).filter(([k]) => k !== "preference")) : undefined)} />
      <dl className="re-resolved mono">
        <div><dt>model</dt><dd>{n.model || "none resolves"}</dd></div>
        {n.fallback && <div><dt>fallback</dt><dd>{n.fallback}</dd></div>}
        <div><dt>price</dt><dd>{priceText(model)} per 1M</dd></div>
        <div><dt>context</dt><dd>{model?.context || n.context || "?"}</dd></div>
        <div><dt>tools</dt><dd>{n.tools ?? "?"}</dd></div>
      </dl>
      {[...n.problems, ...n.warnings].length > 0 && (
        <ul className="re-card-problems">{[...n.problems, ...n.warnings].map((p) => <li key={p}>{p}</li>)}</ul>
      )}
      <div className="re-actions">
        <Button size="sm" onClick={() => showBio(n.agent)} disabled={!n.agent}>Edit bio</Button>
        <Button size="sm" variant="ghost" onClick={() => edit((r) => void agentsOf(r).splice(n.index + 1, 0, JSON.parse(JSON.stringify(entry))))}>Duplicate</Button>
        <Button size="sm" variant="danger" onClick={() => openDialog({ kind: "delete-card", node: n.id })} data-testid="roles-remove-card">Remove</Button>
      </div>
      <p className="muted re-tip">Arrows nudge the card on the canvas, Delete removes it; Ctrl+Z undoes any edit.</p>
    </div>
  );
}
