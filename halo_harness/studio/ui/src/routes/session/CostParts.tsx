// The graphics of Session's Cost panel (3.1.5.0 R3): the context-fill bar
// (context_tokens / context_limit: cyan, amber past 80 %, red past 95 %),
// the spend sparkline beside the ticker (spend.ts samples), and each agent's
// share of the spend as one stacked bar in the agents' own colours
// (shared/hues.ts, the Live column's), every figure in mono. 3.1.8.0 R6: a
// line's cost is the agent's own share (shares.ts) and its model calls are
// "calls", never "turns" (the panel's TURNS are the session's user turns).
import { cost, short } from "../orchestra/format";
import type { AgentRow } from "../fleet/types";
import type { Sample } from "./spend";

/** 12, 4.3k, 1.2M. */
export function tok(n: number | null | undefined): string {
  if (n == null || !isFinite(Number(n))) return "-";
  const v = Number(n);
  return v >= 1e6 ? `${(v / 1e6).toFixed(1)}M` : v >= 1e3 ? `${(v / 1e3).toFixed(1)}k` : String(Math.round(v));
}

export const levelOf = (pct: number) => (pct >= 95 ? "bad" : pct >= 80 ? "warn" : "ok");

export function ContextBar({ used, limit }: { used: number | null | undefined; limit: number | null | undefined }) {
  const u = Number(used) || 0, l = Number(limit) || 0;
  const pct = l > 0 ? Math.min(100, (u / l) * 100) : null;
  const level = pct == null ? "none" : levelOf(pct);
  return (
    <div className="sco-ctx" data-testid="session-cost-context" data-level={level} data-pct={pct == null ? "" : pct.toFixed(1)}
         title={pct == null ? "the session has not said how full its context is yet" : `${u.toLocaleString()} of ${l.toLocaleString()} tokens in the model's context`}>
      <div className="sco-ctx-head">
        <span className="sco-label mono">CONTEXT</span>
        <b className="mono sco-ctx-pct">{pct == null ? "-" : `${Math.round(pct)} %`}</b>
        <span className="mono muted sco-ctx-of">{pct == null ? "not reported yet" : `${tok(u)} / ${tok(l)}`}</span>
      </div>
      <div className="sco-ctx-track" aria-hidden="true">
        <span className="sco-ctx-fill" style={{ width: `${pct ?? 0}%` }} />
        <span className="sco-ctx-tick" style={{ left: "80%" }} />
        <span className="sco-ctx-tick" style={{ left: "95%" }} />
      </div>
    </div>
  );
}

/** The spend since this page opened, as a line; the last point a dot. */
export function Spark({ list, w = 132, h = 30 }: { list: Sample[]; w?: number; h?: number }) {
  const pts = list.length ? list : [];
  const t0 = pts[0]?.t || 0, t1 = pts[pts.length - 1]?.t || 1;
  const lo = Math.min(...pts.map((p) => p.usd), 0), hi = Math.max(...pts.map((p) => p.usd), lo + 1e-6);
  const x = (t: number) => (t1 > t0 ? ((t - t0) / (t1 - t0)) * (w - 4) + 2 : w - 2);
  const y = (v: number) => h - 3 - ((v - lo) / (hi - lo)) * (h - 6);
  const d = pts.map((p, i) => `${i ? "L" : "M"}${x(p.t).toFixed(1)} ${y(p.usd).toFixed(1)}`).join(" ");
  const last = pts[pts.length - 1];
  return (
    <svg className="sco-spark" width={w} height={h} viewBox={`0 0 ${w} ${h}`} data-testid="session-cost-spark" data-points={pts.length} role="img"
         aria-label={`spend over time: ${pts.length} samples`}>
      <title>{pts.length > 1 ? `${cost(pts[0].usd)} to ${cost(last.usd)} since this page opened` : "the spend over time draws here as it rises"}</title>
      <line className="sco-spark-base" x1={0} y1={h - 2} x2={w} y2={h - 2} />
      {pts.length > 1 && <path className="sco-spark-area" d={`${d} L${x(last.t).toFixed(1)} ${h - 2} L${x(pts[0].t).toFixed(1)} ${h - 2} Z`} />}
      {pts.length > 1 && <path className="sco-spark-line" d={d} />}
      {last && <circle className="sco-spark-dot" cx={x(last.t)} cy={y(last.usd)} r={2.6} />}
    </svg>
  );
}

/** `noPrice` (3.3.3.1): this agent's own model reports no price, so its line says so instead of $0.0000. */
export type Share = { a: AgentRow; key: string; hc: number; usd: number; pct: number; noPrice?: boolean };

export function ShareBar({ rows }: { rows: Share[] }) {
  const total = rows.reduce((s, r) => s + r.usd, 0);
  return (
    <div className="sco-share" data-testid="session-cost-share" role="img" aria-label="each agent's share of the spend">
      {total > 0 ? (
        rows.filter((r) => r.usd > 0).map((r) => (
          <span key={r.key} className="sco-share-seg" data-hc={r.hc} data-testid="session-cost-share-seg" data-key={r.key} style={{ flexGrow: r.usd }}
                title={`${r.a.name || r.a.agent_id}: ${cost(r.usd)} (${Math.round(r.pct)} %)`} />
        ))
      ) : (
        <span className="sco-share-none mono muted">no spend yet</span>
      )}
    </div>
  );
}

export function AgentLine({ r }: { r: Share }) {
  const { a } = r;
  return (
    <div className="sco-row" data-state={a.state || "none"} data-testid="session-cost-agent" data-key={r.key}>
      <span className="sco-swatch" data-hc={r.hc} aria-hidden="true" />
      <span className="sco-row-name">{short(a.name || a.role || a.agent_id, 22)}</span>
      <span className="mono muted sco-row-state">{a.state}</span>
      <span className="mono muted sco-row-tok" title="its own tokens in / out, as each of its model calls ends" data-testid="session-cost-agent-tokens">
        {a.tokens_in == null && a.tokens_out == null ? "-" : `${tok(a.tokens_in)} / ${tok(a.tokens_out)}`}
      </span>
      <span className="mono muted sco-row-calls" title="its model calls" data-testid="session-cost-agent-calls">
        {typeof a.turns === "number" ? `${a.turns} call${a.turns === 1 ? "" : "s"}` : "-"}
      </span>
      {r.noPrice ? (
        <b className="mono sco-row-usd sco-noprice" data-testid="session-cost-noprice"
           title={`its model${a.model ? ` ${a.model}` : ""} reports no price: what it spent is not in the total`}>no price</b>
      ) : (
        <b className="mono sco-row-usd" title={a.parent ? "what it spent itself (its finished sub-agents are on their own lines)" : "what it spent itself: the session's total less its finished sub-agents' (on their own lines)"}
           data-testid="session-cost-agent-usd">{cost(r.usd)}</b>
      )}
      <span className="mono muted sco-row-pct">{r.pct > 0 ? `${Math.round(r.pct)} %` : ""}</span>
    </div>
  );
}
