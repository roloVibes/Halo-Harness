// The fit badge's evidence (3.3.6.0 R3; providers/fit_evidence.py): the model's last load on its host as the server
// log (or /api/ps) says it -- "verified -- 41/41 layers, splits = 2, 258 tok/s", "spilled -- 59/66 layers, 16 tok/s"
// or "unverified" -- on the Models rows, the Library row of an installed model and the card's fit block.
export type FitEvidenceView = { state: "verified" | "spilled" | "unverified" | string; line: string; source?: string | null;
  host?: string; why?: string };

export function FitEvidenceChip({ ev, testid = "fit-evidence" }: { ev?: FitEvidenceView | null; testid?: string }) {
  if (!ev || !ev.line) return null;
  const from = ev.source ? `the last load, from ${ev.source}` : ev.why || "no load seen yet on this host";
  return (
    <span className="og-chip mono fe-chip" data-testid={testid} data-state={ev.state} title={ev.host ? `${from} (on ${ev.host})` : from}>
      {ev.line}
    </span>
  );
}
