// Test this lineup (3.3.16.0 R1), on Runs' bar: the guided first run moved here (3.3.15.0 R5/R7: `POST start` rehearses
// the active lineup as it is, nothing copied). The button reads GET start each time Runs shows: on the Auto lineup (or
// none) it is disabled and the Auto line stands beside it; with a lineup of your own it opens the card first -- what
// the run does, the lineup and its cards, the models, the estimated cost, the time, what it writes (start/card.py) --
// and Run starts it; its seven steps then show in the guided first run's panel (shell/StartHere.tsx), as from the
// palette's "Start: the guided first run".
import { useEffect, useState } from "react";
import { api, ApiError } from "../../../lib/api";
import { runStart, start } from "../../../lib/start";
import { Button, Dialog } from "../../../lib/ui";

type Status = { card?: string[]; auto?: string };

export function TestLineup() {
  const [st, setSt] = useState<Status | null>(null);
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const read = () =>
    api.get<Status>("start").then(setSt).catch((e) => setSt({ card: [`the card could not be read: ${e instanceof ApiError ? e.message : String(e)}`], auto: "" }));
  useEffect(() => void read(), []);
  const auto = st?.auto || "";
  const go = async () => {
    setBusy(true);
    setError("");
    try {
      await runStart();
      const s = start.get();
      if (s.view === "run" && s.running) {
        start.update(() => ({ open: true, asked: true })); // its steps, in the guided first run's panel
        setOpen(false);
      } else setError(s.auto || s.error || "");
    } finally {
      setBusy(false);
    }
  };
  return (
    <span className="ag-test">
      <Button size="sm" variant="ghost" disabled={!st || !!auto} onClick={() => (setOpen(true), void read())} data-testid="agents-test-lineup"
              title={auto || "The guided first run on your active lineup: a sample repo, one real goal, the plan, the lanes, the report; its card first"}>
        Test this lineup
      </Button>
      {auto && <span className="ag-test-auto muted" data-testid="agents-test-auto">{auto}</span>}
      <Dialog open={open} onClose={() => setOpen(false)} title="Test this lineup" kicker="AGENTS · RUNS · THE GUIDED FIRST RUN" testid="agents-test"
              footer={<>
                <Button variant="ghost" onClick={() => setOpen(false)}>Cancel</Button>
                <Button variant="primary" onClick={() => void go()} disabled={busy || !!auto || !st?.card?.length} data-testid="agents-test-run">Run it</Button>
              </>}>
        <pre className="sh-card mono" data-testid="agents-test-card">{(st?.card || []).join("\n") || "reading the card..."}</pre>
        <p className="muted">One real Orchestra run on a small sample repo with your active lineup's agents, as <code>halo start</code> runs it in a terminal.</p>
        {(error || auto) && <p className="og-problems" data-testid="agents-test-error">{error || auto}</p>}
      </Dialog>
    </span>
  );
}
