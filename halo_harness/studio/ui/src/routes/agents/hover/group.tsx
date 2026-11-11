// A Live group's hover card (3.3.16.3): what the group is for (the task, or the square's DOES line), who is in it (each
// agent's role on its model), how many are working / waiting / done, what it has cost and for how long, who started it,
// Auto's pick in plain words. A click on the bar's chevron folds it; a click on an agent inside is that agent's.
import { shortModel } from "../../../lib/modelName";
import { HoverBody, type HoverRow } from "../../../lib/hover/HoverBody";
import type { GroupBox } from "../live/groupLayout";
import { countLine, tally } from "../live/GroupBox";
import { joined } from "./words";

const IS: Record<string, string> = {
  task: "Agents started together, by one step of the agent above, for one task.",
  square: "A square's agents: the use case main handed this work to.",
  run: "A goal run's lanes: each a worker in its own worktree, owning the units it claimed, merged one at a time and checked by the gate.",
};

export function GroupHover({ b, now }: { b: GroupBox; now: number }) {
  const g = b.g;
  const ms = b.members.filter((m) => !m.virtual && !m.kind);
  const t = tally(b, now);
  const who = new Map<string, number>();
  for (const m of ms) {
    const k = joined([m.role || m.name, shortModel(m.model) && `on ${shortModel(m.model)}`], " ");
    who.set(k, (who.get(k) || 0) + 1);
  }
  const rows: HoverRow[] = [
    ["For", g.kind === "square" ? g.why : g.title],
    ["Who", [...who].map(([k, n]) => (n > 1 ? `${n} × ${k}` : k)).join(", ")],
    ["Now", countLine(t)],
    ["Started by", b.by],
    ["Picked", g.kind === "square" ? "" : g.why],
    ["Inside", g.outer ? "the group around it" : ""],
  ];
  return <HoverBody title={g.title} is={IS[g.kind] || ""} rows={rows} foot="The chevron folds it to its bar; click an agent for everything" />;
}
