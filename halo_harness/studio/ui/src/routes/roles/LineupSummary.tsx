// 3.3.16.0 R1b, "summary first" (the owner's photo of the Lineup tab, 2026-11-09: "so so busy ... idk what all of
// those functions and settings even are"): with a lineup open, the inspector's body is six plain-words lines -- what
// it does, the main model, who is on it, where workers run, spend, how many sections are set -- then one Edit row per
// block: its title, its state in mono ("mode by-skill, 3 at once", or "not set = Halo does: <the default's first
// clause>"), and Edit. The row's title button keeps its 3.0.7.0 testid (`roles-block-<name>`) and opens the page as
// Edit (`roles-edit-<name>`) does. No form, no YAML box, no help paragraph is on this page.
import { useHelpGroup } from "../../lib/fieldHelp";
import { Button } from "../../lib/ui";
import { blockSet, firstClause, LINEUP_BLOCKS, mainLine, policyLine, spendLine, stateLine, whoLine, workersLine, type LineupBlock } from "./defaults";
import { useSched } from "./LineupSched";
import { openLineupPage } from "./pages";
import { modelRow, useRoles } from "./store";

function SummaryLines() {
  const raw = useRoles((s) => s.raw);
  const graph = useRoles((s) => s.graph);
  const row = useRoles((s) => {
    const m = s.graph?.nodes.find((n) => n.role === "main")?.model || "";
    return modelRow(s, m) || s.fallback.find((x) => x.ref === m);
  });
  const lines: [string, string, string][] = [
    ["does", String(raw?.description || "") || "no description yet", "does"],
    ["main model", mainLine(graph, row, raw), "main"],
    ["on it", whoLine(graph), "who"],
    ["workers run", workersLine(raw), "workers"],
    ["spend", spendLine(raw), "spend"],
    ["policy", policyLine(raw), "policy"],
  ];
  return (
    <dl className="ri-summary" data-testid="roles-summary">
      {lines.map(([label, text, key]) => (
        <div key={key} data-line={key}>
          <dt className="mono">{label}</dt>
          <dd data-muted={(key === "does" && !raw?.description) || undefined}>{text}</dd>
        </div>
      ))}
    </dl>
  );
}

function ScheduleState({ name }: { name: string }) {
  const { got, err } = useSched(name);
  const text = err ? "could not read the swap preview" : !got ? "reading ..." : got.local
    ? `${got.swaps} swap${got.swaps === 1 ? "" : "s"} a pass` : "no local models: nothing to warm";
  return <span className="ri-row-state mono" data-muted={!got?.local || undefined}>{text}</span>;
}

function EditRow({ b }: { b: LineupBlock }) {
  const name = useRoles((s) => s.name);
  const set = useRoles((s) => blockSet(b.id, s.raw));
  const state = useRoles((s) => stateLine(b.id, s.raw));
  const defaults = useHelpGroup("lineup_defaults");
  const dflt = b.defaultKey ? defaults[b.defaultKey] || "" : "";
  const open = () => openLineupPage(b.id);
  return (
    <li className="ri-row" data-density="row" data-block={b.id} data-set={set || undefined}>
      <button className="ri-row-main" onClick={open} data-testid={`roles-block-${b.id}`} title={!set && dflt ? `not set = Halo does: ${dflt}` : undefined}>
        <span className="ri-row-title">{b.title}</span>
        {b.id === "schedule" ? <ScheduleState name={name} />
          : set ? <span className="ri-row-state mono">{state || "set"}</span>
          : <span className="ri-row-state mono" data-muted>{dflt ? `not set = Halo does: ${firstClause(dflt)}` : b.id === "description" ? "no description yet" : "not set"}</span>}
      </button>
      <Button size="sm" variant="ghost" onClick={open} data-testid={`roles-edit-${b.id}`} aria-label={`Edit ${b.title}`}>Edit</Button>
    </li>
  );
}

export function LineupSummary() {
  return (
    <div className="ri-sum" data-testid="roles-lineup-summary">
      <SummaryLines />
      <ul className="ri-rows" aria-label="Edit one block">
        {LINEUP_BLOCKS.map((b) => <EditRow key={b.id} b={b} />)}
      </ul>
    </div>
  );
}
