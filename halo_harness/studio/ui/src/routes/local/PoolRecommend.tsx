// Local -> Pool, the recommendation (3.3.8.0 R1; GET local/pool/recommend): what fits the pool, the fewest active
// parameters first; then what a single node holds (run it there: pooling is unnecessary, ranked last); then what
// does not fit, with its numbers. Each row: the badge, the verdict, the build and batch-only tags, the speed
// (measured elsewhere or extrapolated), every line behind it one click away, and the honest preview before any
// download -- with the one button that names it: Download (the existing Hugging Face download + verify job, the
// licence card first, HfCards.tsx). Nothing downloads until it is pressed.
import { useEffect } from "react";
import { Button } from "../../lib/ui";
import { askDownload, loadDirs, useHf } from "./hfstore";
import { dlJobFor, useJobs } from "./jobs";
import { setBatch, usePool, type Verdict } from "./poolstore";
import { PullBar } from "./Pulls";

const k = (n: number) => (n >= 1024 ? `${Math.round(n / 1024)}k` : String(n));

function PoolDownload({ v }: { v: Verdict }) {
  const dirs = useHf((s) => s.data?.dirs);
  const d = v.download;
  const job = useJobs((s) => (d ? dlJobFor(s, d.repo, d.file) : undefined));
  const said = useHf((s) => (d ? s.said[`dl|${d.repo}|${d.file}`] : undefined));
  useEffect(() => {
    if (!dirs) void loadDirs();
  }, [dirs]);
  if (!d) return null;
  const folders = (dirs || []).filter((x) => x.exists).map((x) => x.path);
  return (
    <span className="pool-dl">
      {(!job || job.done) && (
        <Button size="sm" variant="primary" disabled={!folders.length} onClick={() => void askDownload(d.repo, d.file, folders)}
                data-testid="pool-download" title={folders.length ? `${d.cli}: the licence card first, then the download and its verify`
                  : `add a model folder on Local -> Hugging Face first (${d.cli})`}>
          Download {d.gb} GB
        </Button>
      )}
      {job && <PullBar j={job} />}
      {said && !said.ok && <span className="mono lc-said" data-testid="pool-download-said">{said.text}</span>}
    </span>
  );
}

function Row({ v }: { v: Verdict }) {
  const ctx = v.state === "pool" ? `${k(v.max_ctx_f16)} F16 / ${k(v.max_ctx_q8)} Q8_0` : v.state === "single" ? `${k(v.max_ctx_f16)} F16 on ${v.node}` : "—";
  return (
    <>
      <tr data-testid="pool-rec-row" data-model={v.model} data-state={v.state} data-rank={v.rank ?? undefined}>
        <td className="mono">{v.rank ?? "—"}</td>
        <td><b>{v.display}</b>{v.tags.map((t) => <span key={t} className="og-chip mono pool-tag" data-testid="pool-rec-tag">{t}</span>)}</td>
        <td><span className="pool-badge mono" data-testid="pool-rec-badge" data-state={v.state} title={v.verdict}>{v.badge}</span></td>
        <td className="mono" data-testid="pool-rec-need" title="weights + a routing table per node + 1 GB of buffers per node + the KV cache at 16k F16">
          {v.need_gb != null ? `${v.need_gb.toFixed(1)} of ${(v.free_gb ?? 0).toFixed(1)} GB` : "—"}
        </td>
        <td className="mono" data-testid="pool-rec-ctx">{ctx}</td>
        <td className="mono" data-testid="pool-rec-speed" title={v.lines.find((l) => l.startsWith("speed:")) || ""}>{v.speed_word}</td>
        <td>{v.state !== "no" && <PoolDownload v={v} />}</td>
      </tr>
      <tr className="pool-sub">
        <td colSpan={7}>
          <p className="mono pool-verdict" data-testid="pool-rec-verdict">{v.verdict}</p>
          <p className="mono muted pool-preview" data-testid="pool-rec-preview">{v.preview}</p>
          {v.lines.length > 1 && (
            <details className="pool-lines" data-testid="pool-rec-lines">
              <summary className="mono muted">every number behind it ({v.lines.length - 1})</summary>
              <ul className="mono">{v.lines.slice(1).map((l) => <li key={l}>{l}</li>)}</ul>
            </details>
          )}
        </td>
      </tr>
    </>
  );
}

export function PoolRecommend() {
  const rec = usePool((s) => s.rec);
  const batch = usePool((s) => s.batch);
  if (!rec) return <p className="mono muted">reading the recommendation...</p>;
  const all = [...rec.rows, ...rec.others];
  return (
    <section className="pool-block" data-testid="pool-recommend" data-rows={rec.rows.length} data-others={rec.others.length} aria-label="Recommendation">
      <div className="rail-label mono">WHAT THE POOL CAN RUN · THE FEWEST ACTIVE PARAMETERS FIRST</div>
      <p className="mono" data-testid="pool-rec-head">{rec.head}</p>
      <label className="mono muted pool-batch">
        <input type="checkbox" checked={batch} onChange={(e) => setBatch(e.target.checked)} data-testid="pool-rec-batch" />
        {" "}show the batch-only models (a dense 70B pooled: 3-6 tok/s, a background lane)
      </label>
      <div className="pool-scroll">
        <table className="pool-table">
          <thead><tr><th>#</th><th>model</th><th>pool</th><th>needs of free</th><th>window</th><th>speed</th><th /></tr></thead>
          <tbody>{all.map((v) => <Row key={v.model} v={v} />)}</tbody>
        </table>
      </div>
      {rec.hidden.length > 0 && (
        <ul className="mono muted pool-hidden" data-testid="pool-rec-hidden">{rec.hidden.map((h) => <li key={h.model}>{h.line}</li>)}</ul>
      )}
    </section>
  );
}
