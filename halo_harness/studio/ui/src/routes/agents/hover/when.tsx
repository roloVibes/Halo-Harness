// A block's line's hover card (3.3.16.3): the rule it carries in one sentence ("main hands media work when it needs a PDF
// or audio"), its label, where the rule is written, and what a click does (the When page).
import { HoverBody, type HoverRow } from "../../../lib/hover/HoverBody";
import { squareOf, useWf } from "../workflows/store";
import { whenLabel, writesBoard } from "../blocks/templates";

export function WhenHover({ sqRef }: { sqRef: string }) {
  const q = useWf((s) => squareOf(s, sqRef));
  if (!q) return null;
  const rows: HoverRow[] = [
    ["From", "main"],
    ["To", `${q.ref}: ${q.does || "a square"}`],
    ["When", whenLabel(q)],
    ["Written", q.when && Object.keys(q.when).length ? writesBoard().replace("workflows.enabled", `workflows.when.${q.ref}`) : "nothing of its own: its covers"],
  ];
  return <HoverBody title={`main -> ${q.ref}`} is={q.when_sentence || ""} rows={rows} foot="Click: change when, on one page" />;
}
