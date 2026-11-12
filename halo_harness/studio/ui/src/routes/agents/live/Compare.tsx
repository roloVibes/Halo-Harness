// Compare two runs, a page of History (3.4.1.0 R2 "Time"; compareStore.ts holds what it read). One page, two columns
// over one time axis: for each run its agents as lanes in their blocks (the phase colours: writing, a tool, waiting on
// you), then the rows that answer the question -- how it ended, wall time, cost, tokens, the models (each one's share
// of cost and time), agents spawned, asks to you, failures, retries -- with the better figure named by a word beside it
// (never only a colour; a cost Halo cannot price is "unknown" and not compared), and "what differed" in three plain
// lines derived from the rows. No model call; nothing written. A run compared with itself shows "split at": before /
// after that moment. Back returns to History's list with the ticks kept.
import { useState } from "react";
import { Button } from "../../../lib/ui";
import { short } from "../../orchestra/format";
import { closeReport } from "./historyStore";
import { loadCompare, useCompare, type CmpLane, type CmpRow, type Side } from "./compareStore";
import { mmss } from "./timeline";

const KIND: Record<string, string> = { session: "session", run: "goal run", file: "saved replay" };
const PHASE: Record<string, string> = { writing: "writing", tool: "a tool", waiting: "waiting on you" };
const pct = (v: number, span: number) => `${Math.max(0, Math.min(100, (v / Math.max(1e-6, span)) * 100))}%`;

function Lane({ l, side, span }: { l: CmpLane; side: string; span: number }) {
  const what = `${l.name}${l.role && l.role !== l.name ? ` (${l.role})` : ""} · ${l.model || "model not recorded"} · ${l.state} · ${mmss(l.from)} to ${mmss(l.to)}`;
  return (
    <div className="cmp-lane" data-testid="compare-lane" data-side={side} data-agent={l.agent_id} data-to={Math.round(l.to)} title={what}>
      <span className="cmp-lane-name mono">{l.name}</span>
      <span className="cmp-track" aria-label={what}>
        <span className="cmp-life" data-state={l.state} style={{ left: pct(l.from, span), width: pct(l.to - l.from, span) }} />
        {l.segs.map((s, i) => (
          <span key={i} className="cmp-seg" data-testid="compare-seg" data-phase={s.phase} title={`${PHASE[s.phase] || s.phase}: ${mmss(s.t0)} to ${mmss(s.t1)}`}
                style={{ left: pct(s.t0, span), width: pct(s.t1 - s.t0, span) }} />
        ))}
      </span>
    </div>
  );
}

function Column({ s, span }: { s: Side; span: number }) {
  const blocks = [...new Set(s.lanes.map((l) => l.block))];
  return (
    <div className="cmp-col" data-testid="compare-column" data-side={s.label} data-kind={s.kind} data-id={s.id}>
      <div className="cmp-col-head" title={`${s.label}: ${KIND[s.kind] || s.kind} ${s.id}\n${s.title}`}>
        <b className="cmp-letter mono">{s.label}</b>
        <span className="cmp-col-title">{short(s.title || s.id, 90)}</span>
        <span className="mono muted cmp-col-kind">{KIND[s.kind] || s.kind}{s.figures.window ? ` · ${mmss(s.figures.window[0])} to ${mmss(s.figures.window[1])}` : ""}</span>
      </div>
      <div className="cmp-axis mono muted" aria-hidden="true"><span>0:00</span><span>{mmss(span / 2)}</span><span>{mmss(span)}</span></div>
      {blocks.map((b) => (
        <div key={b} className="cmp-block" data-testid="compare-block" data-block={b}>
          <div className="cmp-block-name mono muted">{b}</div>
          {s.lanes.filter((l) => l.block === b).map((l) => <Lane key={l.agent_id} l={l} side={s.label} span={span} />)}
        </div>
      ))}
      {!s.lanes.length && <p className="muted cmp-none">No agents in this stretch.</p>}
    </div>
  );
}

function Cell({ r, side }: { r: CmpRow; side: "a" | "b" }) {
  const c = r[side];
  const best = r.better === side;
  return (
    <td className="cmp-cell" data-testid="compare-cell" data-side={side} data-better={best || undefined} data-unknown={c.unknown || undefined} title={c.text}>
      <span className="cmp-val">{c.text}</span>
      {best && <span className="cmp-word mono" data-testid="compare-word">{r.word}</span>}
    </td>
  );
}

function Split({ at, span, a }: { at: number; span: number; a: string }) {
  const [v, setV] = useState(mmss(at));
  const secs = (t: string) => t.trim().split(":").map(Number).reduce((x, n) => x * 60 + n, 0);
  const ok = /^\d+(:\d{1,2}){0,2}$/.test(v.trim()) && secs(v) > 0 && secs(v) < span + 1;
  return (
    <label className="cmp-split mono" title="A run compared with itself: A is before this moment, B from it on (by default its first steer, else halfway)">
      split at <input className="input mono" value={v} onChange={(e) => setV(e.target.value)} data-testid="compare-split" />
      <Button size="sm" disabled={!ok} onClick={() => void loadCompare(a, a, secs(v))} data-testid="compare-split-go">Apply</Button>
    </label>
  );
}

export function ComparePage() {
  const data = useCompare((s) => s.data);
  const error = useCompare((s) => s.error);
  const refs = useCompare((s) => s.refs);
  const span = data ? Math.max(1, data.axis.secs) : 1;
  return (
    <div className="cmp" data-testid="history-compare" data-a={refs?.[0]} data-b={refs?.[1]} data-state={error ? "error" : data ? "ready" : "reading"} data-split={data?.split ?? undefined}>
      <div className="rr-head" data-density="bar">
        <Button size="sm" variant="ghost" onClick={closeReport} data-testid="compare-back" title="Back to History's list (the ticks stay)">Back</Button>
        <b className="lh-title">Compare</b>
        <span className="mono muted">from each run's own record · no model call · nothing written</span>
        <span className="spacer" />
        {data && data.split !== null && refs && <Split key={data.split} at={data.split} span={(data.a.figures.wall_s || 0) + (data.b.figures.wall_s || 0)} a={refs[0]} />}
      </div>
      {error ? <p className="field-error" data-testid="compare-error">{error}</p> : !data ? <p className="mono muted">reading both runs...</p> : (
        <>
          <section className="rr-block" aria-label="What differed">
            <div className="rail-label mono">WHAT DIFFERED</div>
            <ol className="cmp-differed" data-testid="compare-differed">{data.differed.map((l, i) => <li key={i} data-testid="compare-line">{l}</li>)}</ol>
          </section>
          <section className="cmp-cols" aria-label="The two runs over one time axis">
            <Column s={data.a} span={span} />
            <Column s={data.b} span={span} />
          </section>
          <table className="cmp-rows" data-testid="compare-rows">
            <thead><tr><th /><th className="mono">A</th><th className="mono">B</th></tr></thead>
            <tbody>
              {data.rows.map((r) => (
                <tr key={r.key} data-testid="compare-row" data-key={r.key} data-better={r.better || undefined} data-word={r.word || undefined}>
                  <th scope="row" className="mono">{r.label}</th>
                  <Cell r={r} side="a" />
                  <Cell r={r} side="b" />
                </tr>
              ))}
            </tbody>
          </table>
          <p className="mono muted cmp-foot">The better figure is named beside it; "same" and "unknown" rows name none. A cost Halo cannot price is unknown, never $0.</p>
        </>
      )}
    </div>
  );
}
