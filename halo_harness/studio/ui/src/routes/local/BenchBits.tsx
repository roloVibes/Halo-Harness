// A Models row's bench bits (3.3.6.0 R5; routes/local/benchstore.ts): Bench beside Probe (its confirmation is the cost
// line: "local: ~N min on <host>, the card is busy meanwhile, writes the speed card; no tokens leave this machine"),
// the live log while it runs, and the speed card's chip -- reply tok/s at the ceiling, the largest window that stayed
// on the GPU, and "measured on 0.40.6" when it is stale.
import { useEffect } from "react";
import { Button } from "../../lib/ui";
import { askBench, benchLine, jobFor, startBenchFeed, useBench } from "./benchstore";
import { BenchConfirm, BenchLog } from "./BenchTable";
import { useLocal } from "./store";
import type { ModelEntry } from "./types";

export function BenchAction({ m, host }: { m: ModelEntry; host: string }) {
  const job = useBench((s) => jobFor(s, host, m.model));
  const ctl = useLocal((s) => s.hosts?.find((h) => h.name === host)?.controls);
  useEffect(() => {
    startBenchFeed();
  }, []);
  const off = ctl && !ctl.ok ? ctl.why : "";
  const running = !!job && !job.done;
  const benched = !!m.card?.speed_card;
  return (
    <Button size="sm" disabled={running || !!off} onClick={() => void askBench(host, m.model)} data-testid="local-model-bench"
            data-benched={benched || undefined} title={off || `the cost line first, then it runs -- ${benchLine(host, m.model)}`}>
      {running ? "Benching..." : benched ? "Re-bench" : "Bench"}
    </Button>
  );
}

export function BenchStrip({ m, host }: { m: ModelEntry; host: string }) {
  return (
    <>
      <BenchConfirm host={host} model={m.model} />
      <BenchLog host={host} model={m.model} />
    </>
  );
}

export function SpeedCardChip({ m }: { m: ModelEntry }) {
  const c = m.card?.speed_card;
  if (!c) return null;
  const top = c.windows.filter((w) => typeof w.tok_s === "number").slice(-1)[0];
  const g = c.max_gpu_window;
  return (
    <span className="og-chip mono" data-testid="local-model-speedcard" data-stale={c.stale || undefined}
          title={c.lines.join("\n")}>
      bench: {top ? `${Math.round(top.tok_s as number)} tok/s at ${Math.round(top.window / 1024)}k` : "no window answered"}
      {g ? ` · GPU to ${Math.round(g / 1024)}k` : " · spills"}{c.stale ? ` · ${c.stale}` : ""}
    </span>
  );
}
