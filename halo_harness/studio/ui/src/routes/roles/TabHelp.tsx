// The `?` of the Inspector's Assignment and Lineup tabs (3.3.15.0 R3, the 3.3.2.0 rule: reference text goes in a `?`):
// the one-line explainer of every field on the tab, field_help.py's lines (lib/fieldHelp.ts), listed by the field's
// label. The fields themselves draw no hint line inside `HintsInHelp` (controls.tsx); the label keeps it as its
// tooltip. 3.3.16.0 R1b: each block's page has its own `?`, that block's lines only (useBlockLines).
import type { ReactNode } from "react";
import { useHelpGroup } from "../../lib/fieldHelp";
import { HintsInHelp } from "./controls";
import { SECTIONS } from "./sections";

export type HelpLine = [label: string, line: string | undefined];

/** The `?` itself: closed it is one small button at the tab's top right; open, a label and its line per field. */
export function TabHelp({ lines, testid }: { lines: HelpLine[]; testid: string }) {
  const shown = lines.filter((l): l is [string, string] => !!l[1]);
  if (!shown.length) return null;
  return (
    <details className="lg-help re-tab-help" data-testid={testid}>
      <summary className="mono" aria-label="what each field is for">?</summary>
      <dl className="re-tab-help-lines">
        {shown.map(([label, line], i) => (
          <div key={i}>
            <dt className="mono">{label}</dt>
            <dd>{line}</dd>
          </div>
        ))}
      </dl>
    </details>
  );
}

/** A tab's body with its fields' hints in its `?`. */
export function InHelp({ children }: { children: ReactNode }) {
  return <HintsInHelp.Provider value>{children}</HintsInHelp.Provider>;
}

/** The lineup header's three fields (Description, How the pieces work together, Extends). */
export function useHeaderLines(): HelpLine[] {
  const h = useHelpGroup("assignment");
  return [["Description", h.description], ["How the pieces work together", h.about], ["Extends", h.extends]];
}

/** 3.3.16.0 R1b: the lines of one block's page (the page's `?` lists that block's fields only). */
export function useBlockLines(block: string): HelpLine[] {
  const h = useHelpGroup("assignment");
  const f = useHelpGroup("lineup_fields");
  const head = useHeaderLines();
  if (block === "description") return head;
  if (block === "workers") return [["Isolation", h.isolation], ["Secrets broker", h.secrets], ["Tool capabilities", h.capabilities]];
  if (block === "schedule") return [["Swaps a pass", "one pass of the lineup: main, each local lane, back to main (the steady state)"],
                                    ["Warm", "load the warm set now, the same as halo local warm <lineup>"]];
  const d = SECTIONS.find((x) => x.name === block);
  return d ? d.fields.map((x): HelpLine => [x.label, f[x.path ? `${d.name}.${x.path}` : d.name]]) : [];
}
