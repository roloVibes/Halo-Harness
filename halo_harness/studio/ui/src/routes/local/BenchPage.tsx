// Local -> Benchmarks (3.3.6.0 R5): three blocks. The speed cards per host (BenchTable.tsx: Bench / Re-bench per row,
// the cost line first, the live log while a job runs), the tuning report (TuneReport.tsx: Apply for Halo's side with a
// scope, the exact line for the server's), and the changes in force with their scopes and Revert (ChangesList.tsx).
// The bench frames keep the table live; a job that ends reads the cards and the Models rows again.
import { useEffect } from "react";
import { BenchTable } from "./BenchTable";
import { ChangesList } from "./ChangesList";
import { loadBenches, startBenchFeed, useBench } from "./benchstore";
import { TuneReport } from "./TuneReport";

export function BenchPage() {
  const error = useBench((s) => s.error);
  useEffect(() => {
    startBenchFeed();
    void loadBenches();
  }, []);
  return (
    <div className="lc-bench" data-testid="local-bench">
      {error && <p className="mono lc-said" data-testid="bench-error">{error}</p>}
      <section className="lc-block" aria-label="Speed cards" data-testid="bench-block" data-block="cards">
        <div className="rail-label mono">SPEED CARDS · THE BENCH ON EACH HOST</div>
        <p className="muted lc-lead">The first call after a load is a warm-up and is never timed; each window is a fixed prompt
          of about 60 % of it and a 256-token reply. A bench needs the card to itself for a few minutes.</p>
        <BenchTable />
      </section>
      <section className="lc-block" aria-label="Tuning report" data-testid="bench-block" data-block="tune">
        <div className="rail-label mono">TUNING REPORT · THE PLANNER'S OPTIONS FOR THE WHOLE HOST</div>
        <TuneReport />
      </section>
      <section className="lc-block" aria-label="Changes" data-testid="bench-block" data-block="changes">
        <div className="rail-label mono">CHANGES · EACH WITH ITS SCOPE</div>
        <ChangesList />
      </section>
    </div>
  );
}
