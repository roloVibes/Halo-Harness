// Hand-offs on the lane timeline (3.0.9.0): a lane that starts after another
// (its `after`, orchestra/handoff_spec.py) is joined to it by an arc in the
// gutter left of the lane cards, and its card carries a chip naming what the
// edge carries (`summary`, `all`, an artifact's name, or `after` when it only
// waits). Every lane shows the commit it started from (`base`).
import { useLayoutEffect, useState, type RefObject } from "react";
import { laneColor } from "./store";
import type { Lane } from "./types";

export type LaneEdge = { from: number; to: number; label: string };

/** What the edge upstream -> lane carries: the takes from that job, else "after". */
export function edgeLabel(lane: Lane, job: string): string {
  const takes = (lane.handoff?.needs || []).filter((n) => n.from === job).map((n) => n.take);
  return takes.length ? [...new Set(takes)].join(" + ") : "after";
}

export function laneEdges(lanes: Lane[]): LaneEdge[] {
  const byJob = new Map(lanes.map((l) => [l.job, l.lane]));
  const out: LaneEdge[] = [];
  for (const l of lanes)
    for (const job of l.after || []) {
      const from = byJob.get(job);
      if (from !== undefined) out.push({ from, to: l.lane, label: edgeLabel(l, job) });
    }
  return out;
}

/** The chips on a lane card: one per upstream, "<- 1 · summary". */
export function EdgeChips({ lane, edges }: { lane: Lane; edges: LaneEdge[] }) {
  const mine = edges.filter((e) => e.to === lane.lane);
  if (!mine.length) return null;
  return (
    <span className="og-lane-chips">
      {mine.map((e) => (
        <span key={e.from} className="og-lane-chip mono" data-testid="lane-edge" data-from={e.from} data-to={e.to} data-lc={laneColor(e.from)}
              title={`lane ${e.to} starts after lane ${e.from}, from its finished head; it takes: ${e.label}`}>
          {"←"} {e.from} · {e.label}
        </span>
      ))}
    </span>
  );
}

export function BaseLine({ lane }: { lane: Lane }) {
  const base = lane.base || "";
  return (
    <span className="og-lane-base mono" data-testid="lane-base" title={base ? `this lane's worktree started from ${base}` : "not started yet"}>
      base: {base ? base.slice(0, 7) : "-"}
    </span>
  );
}

/** The arcs in the gutter, from each upstream card's middle to its lane's. */
export function EdgeArcs({ edges, box, lanes }: { edges: LaneEdge[]; box: RefObject<HTMLDivElement | null>; lanes: Lane[] }) {
  const [ys, setYs] = useState<Record<number, number>>({});
  const [h, setH] = useState(0);
  useLayoutEffect(() => {
    const el = box.current;
    if (!el || !edges.length) return;
    const measure = () => {
      const out: Record<number, number> = {};
      el.querySelectorAll<HTMLElement>('[data-testid="lane"]').forEach((n) => (out[Number(n.dataset.lane)] = n.offsetTop + n.offsetHeight / 2));
      setYs((prev) => (JSON.stringify(prev) === JSON.stringify(out) ? prev : out));
      setH(el.scrollHeight);
    };
    measure();
    const ro = typeof ResizeObserver === "undefined" ? null : new ResizeObserver(measure);
    ro?.observe(el);
    return () => ro?.disconnect();
  }, [edges.length, lanes.length, box]);
  if (!edges.length) return null;
  return (
    <svg className="og-lane-arcs" width={26} height={Math.max(h, 1)} aria-hidden="true">
      {edges.map((e, i) => {
        const y1 = ys[e.from] ?? 0, y2 = ys[e.to] ?? 0;
        const x = 6 + (i % 3) * 4;
        return (
          <path key={`${e.from}>${e.to}`} className="og-lane-arc" data-lc={laneColor(e.from)} d={`M24 ${y1} C${x} ${y1} ${x} ${y2} 24 ${y2}`} />
        );
      })}
    </svg>
  );
}
