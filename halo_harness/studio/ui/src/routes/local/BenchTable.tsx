// Benchmarks, block one (3.3.6.0 R5): per host every installed model's speed card as a row -- the cold load, the
// reply tok/s at each window it tried, the largest window that stayed on the GPU (with the planner's number when
// they differ), the reply reserve below which replies were cut, the Ollama version it was measured on and the stale
// mark ("measured on 0.40.6": a newer Ollama or a changed tag since) -- with Bench / Re-bench, whose confirmation is
// the cost line, and the job's live log while it runs (`bench` frames).
import { Button } from "../../lib/ui";
import { askBench, benchLine, cancelConfirm, jobFor, startBench, useBench, type BenchModel, type SpeedCard } from "./benchstore";

const k = (n: number | null | undefined) => (typeof n === "number" ? (n >= 1024 ? `${Math.round(n / 1024)}k` : String(n)) : "?");
const day = (t: number) => new Date(t * 1000).toISOString().slice(0, 10);

function Windows({ c }: { c: SpeedCard }) {
  return (
    <span className="bench-windows mono">
      {c.windows.map((w) => (
        <span key={w.window} className="bench-win" data-testid="bench-window" data-window={w.window} data-gpu={w.on_gpu === null ? "?" : String(w.on_gpu)}
              title={w.error || `prompt ${w.prompt_tok_s ?? "?"} tok/s · first token ${w.ttft_ms ?? "?"} ms · ${w.on_gpu ? "on the GPU" : w.on_gpu === false ? "spills to the CPU" : "placement unknown"}`}>
          {k(w.window)} {w.tok_s ?? "?"}{w.on_gpu === false ? " (spills)" : ""}
        </span>
      ))}
    </span>
  );
}

export function BenchConfirm({ host, model }: { host: string; model: string }) {
  const c = useBench((s) => (s.confirm && s.confirm.host === host && s.confirm.model === model ? s.confirm : null));
  if (!c) return null;
  return (
    <div className="bench-confirm mono" data-testid="bench-confirm">
      <span data-testid="bench-cost">{c.cost}</span>
      <Button size="sm" variant="primary" onClick={() => void startBench(host, model, c.quick)} data-testid="bench-go"
              title={benchLine(host, model, c.quick)}>Run the bench</Button>
      <Button size="sm" variant="ghost" onClick={cancelConfirm}>Not now</Button>
    </div>
  );
}

export function BenchLog({ host, model }: { host: string; model: string }) {
  const job = useBench((s) => jobFor(s, host, model));
  const said = useBench((s) => s.said[`${host}|${model}`]);
  if (said && !said.ok) return <div className="mono lc-said" data-testid="bench-said">{said.text}</div>;
  if (!job || (job.done && job.ok)) return null;
  return (
    <ol className="bench-log mono" data-testid="bench-log" data-done={job.done || undefined}>
      {(job.lines.length ? job.lines : [job.line]).map((l, i) => <li key={`${i}-${l}`}>{l}</li>)}
      {job.done && !job.ok && <li className="bench-err">{job.error}</li>}
    </ol>
  );
}

function Row({ host, m }: { host: string; m: BenchModel }) {
  const job = useBench((s) => jobFor(s, host, m.model));
  const c = m.card;
  const running = !!job && !job.done;
  return (
    <>
      <tr data-testid="bench-row" data-host={host} data-model={m.model} data-stale={c?.stale || undefined} data-benched={!!c || undefined}>
        <td className="mono"><b>{m.model}</b></td>
        <td className="mono" title="the first load after an unload (load_duration)">{c?.cold_load_s != null ? `${c.cold_load_s} s` : "—"}</td>
        <td>{c ? <Windows c={c} /> : <span className="muted">not benched</span>}</td>
        <td className="mono" data-testid="bench-gpu" title={c?.planner_window && c.planner_window !== c.max_gpu_window ? `the planner says ${k(c.planner_window)}` : "the largest window the bench saw stay on the GPU"}>
          {c ? k(c.max_gpu_window) : "—"}{c?.planner_window && c.planner_window !== c.max_gpu_window ? ` (plan ${k(c.planner_window)})` : ""}
        </td>
        <td className="mono" title="the smallest reply room at which a 256-token reply was not cut">{c ? (c.reserve_floor ?? "over 512") : "—"}</td>
        <td className="mono muted" data-testid="bench-version">
          {c ? `${c.ollama_version || "?"} · ${day(c.at)}` : ""}
          {c?.stale && <span className="og-chip mono bench-stale" data-testid="bench-stale" title="re-bench to measure it again">{c.stale}</span>}
        </td>
        <td>
          <Button size="sm" disabled={running} onClick={() => void askBench(host, m.model)} data-testid="bench-run" title={benchLine(host, m.model)}>
            {running ? "Benching..." : c ? "Re-bench" : "Bench"}
          </Button>
        </td>
      </tr>
      <tr className="bench-sub"><td colSpan={7}><BenchConfirm host={host} model={m.model} /><BenchLog host={host} model={m.model} /></td></tr>
    </>
  );
}

export function BenchTable() {
  const hosts = useBench((s) => s.hosts);
  if (!hosts) return <p className="mono muted">reading the speed cards...</p>;
  if (!hosts.length) return <p className="mono muted" data-testid="bench-none">No Ollama host is configured (ollama.hosts).</p>;
  return (
    <div className="bench-hosts">
      {hosts.map((h) => (
        <div key={h.name} className="bench-host" data-testid="bench-host" data-host={h.name}>
          <div className="rail-label mono">{h.name} · Ollama {h.version || "?"}</div>
          <table className="bench-table">
            <thead><tr><th>model</th><th>cold load</th><th>reply tok/s per window</th><th>GPU up to</th><th>reserve</th><th>measured on</th><th /></tr></thead>
            <tbody>{h.models.map((m) => <Row key={m.model} host={h.name} m={m} />)}</tbody>
          </table>
        </div>
      ))}
    </div>
  );
}
