// The plan canvas's pieces (3.0.9.0 R2), in the Roles canvas look: a layer
// box (one per DAG layer, labelled "at once" / "after job-1, job-3", plus the
// empty "a new layer" box at the end), a lane card (its id and worker, the
// title, the claims as chips, bio and model, the first problem in red), and
// the `after` edges with R1's label chip (summary / all / an artifact's
// name, else "after"). Cards and boxes are memoised. 3.1.2.0 R2: a card shows
// its lane's cost forecast as a chip in its header (data-testid plan-cost).
import { memo, type PointerEvent } from "react";
import { CARD_H, CARD_W, edgePath, type Box, type Pos } from "./layout";
import { costText, costTitle } from "./forecast";
import type { ForecastLine, PlanJob, PlanProblem } from "./types";

type BoxProps = { k: number; b: Box; label: string; count: number; empty: boolean; hot: boolean };

export const LayerBox = memo(function LayerBox({ k, b, label, count, empty, hot }: BoxProps) {
  return (
    <div className="rc-tier pc-layer" data-testid="plan-layer" data-layer={k} data-empty={empty || undefined} data-hot={hot || undefined}
         data-index={k === 0 ? 0 : undefined} style={{ left: b.x, top: b.y, width: b.w, height: b.h }}>
      <div className="rc-tier-head pc-layer-head" title={empty ? "Drop a lane here: it runs after the lanes of the box before" : label}>
        <span className="rc-tier-label">{empty ? "a new layer" : label}</span>
        <span className="rc-tier-count mono">{empty ? "drop here" : `${count} lane${count === 1 ? "" : "s"}`}</span>
      </div>
    </div>
  );
});

type CardProps = {
  job: PlanJob;
  n: number;
  p: Pos;
  layer: number;
  problems: PlanProblem[];
  selected: boolean;
  dragging: boolean;
  cost?: ForecastLine;
  onDown: (ev: PointerEvent<HTMLElement>, id: string) => void;
};

export const LaneCard = memo(function LaneCard({ job, n, p, layer, problems, selected, dragging, cost, onDown }: CardProps) {
  const claims = job.claims || [];
  return (
    <article className="rc-card pc-card" style={{ left: p.x, top: p.y, width: CARD_W, height: CARD_H }} data-testid="plan-lane" data-id={job.id}
             data-layer={layer} data-selected={selected || undefined} data-dragging={dragging || undefined} data-problem={problems.length || undefined}
             data-lc={String((n - 1) % 10)} aria-label={`${job.id}: ${job.title || "no title"}`} onPointerDown={(ev) => onDown(ev, job.id)}
             title="Click to edit it in the inspector; drag it into another box to change what it runs after">
      <span className="rc-band" aria-hidden="true" />
      <header className="rc-head">
        <b className="mono pc-id">{job.id}</b>
        {cost && (
          <span className="og-chip mono pc-cost" data-testid="plan-cost" data-priced={cost.priced || undefined} data-source={cost.source} title={costTitle(cost)}>
            {costText(cost)}
          </span>
        )}
        <span className="rc-scope mono">lane {n}</span>
      </header>
      <div className="pc-title">{job.title || <span className="muted">(no title yet)</span>}</div>
      <div className="pc-claims">
        {claims.slice(0, 3).map((c) => <span key={c} className="og-chip mono" title={c}>{c.split("#")[1] || c}</span>)}
        {claims.length > 3 && <span className="og-chip mono">+{claims.length - 3}</span>}
        {!claims.length && <span className="muted mono">no claims</span>}
      </div>
      <div className="rc-meta mono" title={`bio ${job.bio || "(the goal's worker role)"} · model ${job.model || "(the bio's or the role's)"}`}>
        <span>{job.bio || "worker role"}</span>
        <span>{job.model ? job.model.replace(/^or:[^/]+\//, "") : "default model"}</span>
      </div>
      {problems.length > 0 && (
        <div className="pc-card-problem" data-testid="plan-card-problem" title={problems.map((x) => x.text).join("\n")}>
          {problems[0].text}{problems.length > 1 ? ` (+${problems.length - 1})` : ""}
        </div>
      )}
    </article>
  );
});

export type PlanEdge = { from: string; to: string; label: string };

export function Edges({ edges, pos, w, h, sel }: { edges: PlanEdge[]; pos: Record<string, Pos>; w: number; h: number; sel: string }) {
  return (
    <>
      <svg className="rc-edges" width={w} height={h} aria-hidden="true">
        <defs>
          <marker id="pc-arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">
            <path d="M0,0 L10,5 L0,10 z" className="pc-arrow" />
          </marker>
        </defs>
        {edges.map((e) => {
          const a = pos[e.from], b = pos[e.to];
          if (!a || !b) return null;
          return (
            <path key={`${e.from}>${e.to}`} className="rc-edge pc-edge" d={edgePath(a, b).d} markerEnd="url(#pc-arrow)" data-testid="plan-edge"
                  data-from={e.from} data-to={e.to} data-label={e.label} data-on={sel === e.from || sel === e.to || undefined} />
          );
        })}
      </svg>
      {edges.map((e) => {
        const a = pos[e.from], b = pos[e.to];
        if (!a || !b) return null;
        const { mx, my } = edgePath(a, b);
        return (
          <span key={`chip-${e.from}>${e.to}`} className="og-chip mono pc-edge-chip" style={{ left: mx, top: my }} data-testid="plan-edge-label">
            {e.label}
          </span>
        );
      })}
    </>
  );
}
