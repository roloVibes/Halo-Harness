// 3.3.7.0 R3: the Lineup tab's LOCAL MODELS block -- the open lineup's swap preview (GET local/sched?lineup=<name>,
// studio/local_sched_api.py over local_sched/preview.py): the warm set per card, what one pass of the lineup costs
// in swaps and seconds of loading, and the hygiene lines (verify and worker on different weights, a lane that never
// fits beside main, a `warm:` list that cannot co-reside). Warm loads the warm set now (POST local/warm, the same
// as `halo local warm <lineup>`); its rows arrive as each model lands. Nothing shows for a lineup with no local lanes
// (3.3.16.0 R1b: on its own page, `empty`, one line says so).
import { useCallback, useEffect, useState } from "react";
import { api } from "../../lib/api";
import { Button } from "../../lib/ui";
import { msg } from "./sync";

type Run = { running?: boolean; rows?: string[]; line?: string };
type Sched = { lineup: string; lines: string[]; hygiene: string[]; swaps: number; swap_s: number; local: boolean; warm_run?: Run };

/** The swap preview of lineup `name` (3.3.16.0 R1b: the summary's Schedule row reads it too); it re-reads while Warm runs. */
export function useSched(name: string) {
  const [got, setGot] = useState<Sched | null>(null);
  const [err, setErr] = useState("");
  const read = useCallback(async () => {
    try {
      setGot(await api.get<Sched>("local/sched", { lineup: name }));
      setErr("");
    } catch (e) {
      setGot(null);
      setErr(msg(e));
    }
  }, [name]);
  useEffect(() => {
    void read();
  }, [read]);
  const running = !!got?.warm_run?.running;
  useEffect(() => {
    if (!running) {
      return;
    }
    const id = window.setTimeout(() => void read(), 1000);
    return () => window.clearTimeout(id);
  }, [got, running, read]);
  return { got, err, setErr, read, running };
}

export function LineupSched({ name, empty }: { name: string; empty?: boolean }) {
  const { got, err, setErr, read, running } = useSched(name);
  const warm = async () => {
    try {
      await api.post("local/warm", { lineup: name });
      void read();
    } catch (e) {
      setErr(msg(e));
    }
  };
  if (!got || !got.local) {
    if (err) return <p className="muted" data-testid="roles-lineup-sched-error">{err}</p>;
    return empty && got ? <p className="muted" data-testid="roles-lineup-sched-none">No card of this lineup runs on a local model: nothing to warm.</p> : null;
  }
  const run = got.warm_run || {};
  return (
    <section className="re-block" data-open data-testid="roles-lineup-sched" data-swaps={got.swaps}>
      <header className="re-block-head">
        <b>Local models</b>
        <span className="og-chip mono" title="one pass of the lineup: main, each lane, back to main (the steady state)">
          {got.swaps ? `${got.swaps} swap${got.swaps === 1 ? "" : "s"} a pass` : "0 swaps a pass"}
        </span>
      </header>
      <ul className="re-sched-lines">
        {got.lines.map((l) => <li key={l} className="mono" data-testid="roles-lineup-sched-line">{l}</li>)}
      </ul>
      {got.hygiene.length > 0 && (
        <ul className="re-sched-hygiene">
          {got.hygiene.map((l) => <li key={l} className="muted" data-testid="roles-lineup-sched-hygiene">{l}</li>)}
        </ul>
      )}
      <div className="re-yaml-row">
        <Button size="sm" disabled={running} onClick={() => void warm()} data-testid="roles-lineup-warm"
                title={`halo local warm ${name}: load the warm set now (what is resident stays; the rest pivots later)`}>
          {running ? "Warming..." : "Warm"}
        </Button>
        {run.line && !running && <span className="mono muted" data-testid="roles-lineup-warm-line">{run.line}</span>}
        {err && <span className="og-problems">{err}</span>}
      </div>
      {(run.rows || []).length > 0 && (
        <ul className="re-sched-lines">
          {(run.rows || []).map((l, i) => <li key={`${i}|${l}`} className="mono muted" data-testid="roles-lineup-warm-row">{l}</li>)}
        </ul>
      )}
    </section>
  );
}
