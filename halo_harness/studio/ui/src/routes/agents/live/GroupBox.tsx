// A group box on Live (3.3.16.3, groups.ts says who is in it, groupLayout.ts where): a title bar -- the chevron that
// folds it, the task (or `square <name>`), then one line of counts (N agents, how many working / waiting / done, its
// cost, how long), then the second line when there is one (Auto's pick in plain words, a square's DOES) -- over the box
// its agents sit in. Folded, the bar alone stays, in the strongest state's colour, and lit amber while one of its agents
// waits on you. The parent's line comes into the bar's top (GroupEdges). Hover: the group's card; a click on an agent
// inside is that agent's.
import type { KeyboardEvent } from "react";
import { useHover } from "../../../lib/hover/useHover";
import { cost } from "../../orchestra/format";
import { GroupHover } from "../hover/group";
import type { GroupBox as Box } from "./groupLayout";
import { toggleGroup } from "./groupStore";

const WORKING = ["queued", "running", "paused"];
const FINISHED = ["done", "failed", "stopped"];
const RANK: Record<string, number> = { failed: 4, waiting: 3, working: 2, done: 1 };

export function took(s: number): string {
  const v = Math.max(0, Math.round(s));
  return v < 60 ? `${v}s` : v < 3600 ? `${Math.floor(v / 60)}m ${v % 60}s` : `${Math.floor(v / 3600)}h ${Math.floor((v % 3600) / 60)}m`;
}

/** The members' counts, cost, elapsed seconds and strongest glow (the hover card and the timeline say the same). */
export function tally(b: Pick<Box, "members">, now: number) {
  const ms = b.members.filter((m) => !m.virtual && !m.kind);
  const n = (f: (s: string) => boolean) => ms.filter((m) => f(m.state)).length;
  const t0 = Math.min(...ms.map((m) => m.started || Infinity));
  const live = ms.some((m) => !FINISHED.includes(m.state));
  const t1 = live ? now / 1000 : Math.max(...ms.map((m) => m.ended || m.started || 0));
  const glow = ms.reduce((g, m) => ((RANK[m.glow] || 0) > (RANK[g] || 0) ? m.glow : g), "" as string);
  return { count: ms.length, working: n((s) => WORKING.includes(s)), waiting: n((s) => s === "waiting"), done: n((s) => s === "done" || s === "stopped"),
           failed: n((s) => s === "failed"), cost: ms.reduce((s, m) => s + (Number(m.cost) || 0), 0), secs: isFinite(t0) && t1 > t0 ? t1 - t0 : 0, glow };
}

export function countLine(t: ReturnType<typeof tally>): string {
  const parts = [`${t.count} agent${t.count === 1 ? "" : "s"}`, t.working && `${t.working} working`, t.waiting && `${t.waiting} waiting`,
                 t.done && `${t.done} done`, t.failed && `${t.failed} failed`, cost(t.cost), t.secs ? took(t.secs) : ""];
  return parts.filter(Boolean).join(" · ");
}

/** The box behind its agents (drawn before them); its bar is GroupBar, drawn after them (so Tab reaches the agents first). */
export function GroupBox({ b, now }: { b: Box; now: number }) {
  const t = tally(b, now);
  const g = b.g;
  return (
    <div className="lg-box" style={{ left: b.x, top: b.y, width: b.w, height: b.h }} data-testid="live-group" data-group={g.id} data-kind={g.kind}
         data-engine={g.engine || undefined} data-open={b.open || undefined} data-glow={t.glow || undefined} data-asks={t.waiting > 0 || undefined}
         data-count={t.count} data-outer={g.outer || undefined} />
  );
}

export function GroupBar({ b, now, hover = true }: { b: Box; now: number; hover?: boolean }) {
  const t = tally(b, now);
  const g = b.g;
  const hv = useHover("group", g.id, () => <GroupHover b={b} now={now} />, hover);
  const onKey = (e: KeyboardEvent<HTMLDivElement>) => (e.key === "Enter" || e.key === " ") && e.target === e.currentTarget && (e.preventDefault(), toggleGroup(g.id));
  return (
    <div className="lg-bar" role="button" tabIndex={0} aria-expanded={b.open} aria-label={`${g.title}: ${b.open ? "fold" : "open"} the group`}
         onKeyDown={onKey} style={{ left: b.x, top: b.y, width: b.w, height: b.head }} data-testid="live-group-bar" data-group={g.id}
         data-kind={g.kind} data-open={b.open || undefined} data-glow={t.glow || undefined} data-asks={t.waiting > 0 || undefined} {...hv.props}>
      <div className="lg-row">
        <button className="lg-chev" onClick={() => toggleGroup(g.id)} aria-label={b.open ? "Fold the group to its title bar" : "Open the group"}
                title={hv.titles ? (b.open ? "Fold it to this bar" : "Open it") : undefined} data-testid="live-group-toggle" data-hover-skip>
          {b.open ? "▾" : "▸"}
        </button>
        <b className="lg-title" data-testid="live-group-title" title={hv.titles ? g.title : undefined}>{g.title}</b>
      </div>
      <div className="lg-counts mono" data-testid="live-group-counts">{countLine(t)}</div>
      {g.why && <div className="lg-why mono" data-testid="live-group-why" title={hv.titles ? g.why : undefined}>{g.why}</div>}
    </div>
  );
}

/** The parent's line into each group's title bar (the agents inside have none of their own from the parent). */
export function GroupEdges({ boxes, w, h }: { boxes: Box[]; w: number; h: number }) {
  return (
    <svg className="rlm-edges" width={w} height={h} viewBox={`0 0 ${w} ${h}`} aria-hidden="true">
      {boxes.filter((b) => b.d).map((b) => {
        const glow = tally(b, Date.now()).glow;
        return <path key={b.g.id} className="rlm-edge" d={b.d} data-testid="roles-live-edge" data-from={b.from || undefined} data-to={b.g.id}
                     data-group={b.g.id} data-glow={glow || undefined} />;
      })}
    </svg>
  );
}
