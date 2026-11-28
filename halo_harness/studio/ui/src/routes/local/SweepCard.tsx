// 3.6.0.25 T: the "Find the best window" card a Models row's actions menu opens (beside "Make a tuned twin"): what a
// sweep does before it starts (loads, about how long, that it unloads what is loaded and puts it back, that nothing is
// written to the Ollama store), its running lines with Stop, then the windows as a small table, the pick marked with
// its reason, and the two things a pick can do: Use in Halo (a profile window through Changes) and Make the twin.
import { useEffect, useState } from "react";
import { Button } from "../../lib/ui";
import { makeTwin, planTwin, useCtl } from "./ctl";
import { msg, readSweep, removeNote, startSweep, startTuner, stopSweep, stopTuner, useInHalo } from "./sweep";
import { cells, HEAD, running, startButton, type SweepAnswer } from "./sweepRows";
import { TunerBits } from "./TunerBits";
import type { ModelEntry } from "./types";

export function SweepCard({ host, m }: { host: string; m: ModelEntry }) {
  const [a, setA] = useState<SweepAnswer | null>(null);
  const [said, setSaid] = useState("");
  const plan = useCtl((c) => c.plan);
  const busy = useCtl((c) => c.busy);
  const read = async () => {
    try {
      setA(await readSweep(host, m.model));
    } catch (e) {
      setSaid(msg(e));
    }
  };
  const live = running(a);
  const poll = live || (!!a?.tuner_job && !a.tuner_job.done);
  const pick = a?.sweep?.pick ?? null;
  useEffect(() => { void read(); }, [host, m.model]); // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => {
    if (!poll) return undefined;
    const t = setInterval(() => void read(), 1500);
    return () => clearInterval(t);
  }, [poll]); // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => {
    if (pick && !live) void planTwin(host, m.model, pick);
  }, [host, m.model, pick, live]);
  const act = async (fn: () => Promise<unknown>) => {
    setSaid("");
    try {
      const r = await fn();
      if (typeof r === "string") setSaid(r);
    } catch (e) {
      setSaid(msg(e));
    }
    void read();
  };
  const sw = a?.sweep;
  const go = startButton(sw);
  return (
    <div className="lc-act-body lc-sweep" data-testid="local-sweep" data-running={live || undefined}>
      <p className="lc-why" data-testid="local-sweep-offer" title="what a sweep does, what it costs, what it writes">
        {a ? a.offer : "reading the sweep…"}
      </p>
      <div className="lc-sweep-go">
        {live ? (
          <Button size="sm" onClick={() => void act(() => stopSweep(host, m.model))} data-testid="local-sweep-stop"
                  title="stops after the running load; what was measured is kept">Stop</Button>
        ) : (
          <Button size="sm" variant="primary" disabled={!a} onClick={() => void act(() => startSweep(host, m.model, go.again))}
                  data-testid="local-sweep-start" title={go.title || a?.cli}>{go.label}</Button>
        )}
      </div>
      {a?.job && (live || !sw) && (
        <ul className="lc-sweep-lines mono muted" data-testid="local-sweep-lines">
          {(a.job.lines.length ? a.job.lines : [a.job.line]).slice(-6).map((x, i) => <li key={i}>{x}</li>)}
        </ul>
      )}
      {sw && sw.windows.length > 0 && (
        <table className="lc-sweep-table mono" data-testid="local-sweep-table">
          <thead><tr>{HEAD.map((h, i) => <th key={i}>{h}</th>)}</tr></thead>
          <tbody>
            {sw.windows.map((r) => (
              <tr key={r.window} data-window={r.window} data-pick={r.window === pick || undefined} data-slow={r.slow || undefined}>
                {cells(r, pick).map((c, i) => <td key={i}>{c}</td>)}
              </tr>
            ))}
          </tbody>
        </table>
      )}
      {sw && !live && (
        <p className="lc-why" data-testid="local-sweep-pick">{pick ? `the pick: ${sw.why}` : `no pick: ${sw.why}`}</p>
      )}
      {sw && !live && pick && sw.safe_line ? (
        <p className="lc-why" data-testid="local-sweep-safe">{sw.safe_line}</p>
      ) : null}
      {pick && !live ? (
        <div className="lc-sweep-acts" data-testid="local-sweep-acts">
          <p className="lc-why">{a?.use}</p>
          <Button size="sm" variant="primary" onClick={() => void act(() => useInHalo(host, m.model))} data-testid="local-sweep-use"
                  title={a?.use || ""}>Use in Halo</Button>
          <p className="lc-why" data-testid="local-sweep-twin-says">
            {plan ? `${plan.line}; costs ${plan.cost}` : `makes the tuned twin at ${pick.toLocaleString("en-US")}: a second name in the Ollama store`}
          </p>
          <Button size="sm" disabled={busy} onClick={() => void makeTwin(host, m.model, pick)} data-testid="local-sweep-twin"
                  title={plan?.cli || ""}>Make the twin</Button>
        </div>
      ) : null}
      {a && !live && (
        <TunerBits a={a} start={() => void act(() => startTuner(host, m.model))} stop={() => void act(() => stopTuner(host, m.model))}
                   remove={(kind) => void act(() => removeNote(host, m.model, kind))} />
      )}
      {said && <p className="mono lc-said" data-testid="local-sweep-said">{said}</p>}
      <code className="mono lc-cli-line" title="the same from a terminal">{a?.cli || `halo local bench --host ${host} --sweep ${m.model}`}</code>
    </div>
  );
}
