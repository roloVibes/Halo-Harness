// team-board (3.0.8.0 R2): the team as one board under its run bar.
// Members are columns, stages boxes in the columns of their members, blocks
// nodes in the band underneath, laid out in code (layout.ts). Edges:
// `stage_done:` triggers down the right-hand gutter (they light once the
// stage they wait on is done), reads dashed and writes solid between a stage
// and its blocks (lit while the stage runs), `block_change:` triggers from a
// block to its stage. A click selects a member, a stage or a block and the
// Inspector opens on it. The board fits its panel (scaled down to 75% at the
// most; past that the panel scrolls).
import { useEffect, useMemo, useRef, useState } from "react";
import type { MotionState } from "../../lib/motion";
import { Empty } from "../../lib/ui";
import { layoutStore, patchPanel } from "../../lib/workspace/persist";
import { Metric } from "../orchestra/bits";
import { select } from "./actions";
import { BlockNode, EdgeView, MemberColumn, StageNode } from "./BoardParts";
import { layout, type Edge } from "./layout";
import { RunBar } from "./RunBar";
import { claimState, doc, gatedRows, NONE, rows, runningCount, useTeam, type TeamState } from "./store";
import type { Selection, StageRow } from "./types";

function pick(sel: Selection): void {
  select(sel);
  const l = layoutStore("team").get().layout?.["team-inspector"];
  if (l?.collapsed) patchPanel("team", "team-inspector", { collapsed: false }, false);
}

function litOf(e: Edge, byId: Map<string, StageRow>, s: TeamState): boolean {
  if (e.kind === "done") return byId.get(e.from)?.state === "done";
  if (e.kind === "change") {
    const st = byId.get(e.to)?.state;
    return st === "ready" || st === "running" || claimState(s.blocks.find((b) => b.id === e.from)) === "writing";
  }
  return byId.get(e.from)?.state === "running";
}

const MIN_SCALE = 0.75;

export function TeamBoard({ room }: { room: { w: number; h: number } }) {
  const s = useTeam((x) => x);
  const d = doc(s);
  const rowList = rows(s);
  const memberKey = rowList.map((r) => `${r.id}=${r.members.join(",")}`).join(";");
  const geo = useMemo(() => {
    if (!d) return null;
    const members: Record<string, string[]> = {};
    for (const r of rowList) members[r.id] = r.members;
    return layout(d, members);
  }, [d, memberKey]); // the rows' members, not the rows: a state move keeps the geometry
  if (!d || !geo) return null;
  const byId = new Map(rowList.map((r) => [r.id, r]));
  const sel = s.sel;
  const liveOf = (name: string) => rowList.filter((r) => r.state === "running" && r.members.includes(name)).map((r) => ({ stage: r.id, waiting: r.waiting }));
  return (
    <svg className="tm-svg" viewBox={`0 0 ${geo.width} ${geo.height}`} width={geo.width * fit(geo, room)} height={geo.height * fit(geo, room)} role="img" aria-label={`Team ${d.name}`} data-testid="team-board-svg">
      <defs>
        {(["tm-arrow", "tm-arrow-change", "tm-arrow-dim"] as const).map((id) => (
          <marker key={id} id={id} viewBox="0 0 8 8" refX="7" refY="4" markerWidth="7" markerHeight="7" orient="auto"><path d="M0 0L8 4L0 8z" className={id} /></marker>
        ))}
        <marker id="tm-arrow-read" viewBox="0 0 8 8" refX="1" refY="4" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M0 0L8 4L0 8z" className="tm-arrow-dim" /></marker>
      </defs>
      <g className="tm-band" data-testid="team-blocks-band">
        <rect x={geo.band.x} y={geo.band.y} width={geo.band.w} height={geo.band.h} rx={14} />
        <text x={geo.band.x + 14} y={geo.band.y + 17}>BLOCKS · WHERE THE WORK LANDS</text>
      </g>
      {geo.columns.map((c) => {
        const m = d.members[c.index];
        return <MemberColumn key={c.member} c={c} m={m} live={liveOf(m.name)} sel={sel?.kind === "member" && sel.id === m.name} onClick={() => pick({ kind: "member", id: m.name })} />;
      })}
      <g className="tm-edges">
        {geo.edges.filter((e) => e.kind !== "done").map((e) => <EdgeView key={e.key} e={e} lit={litOf(e, byId, s)} />)}
      </g>
      {geo.stages.map((b) => (
        <StageNode key={b.id} b={b} row={byId.get(b.id)} sel={sel?.kind === "stage" && sel.id === b.id} onClick={() => pick({ kind: "stage", id: b.id })} />
      ))}
      {geo.blocks.map((b) => {
        const spec = d.blocks.find((x) => x.id === b.id)!;
        return (
          <BlockNode key={b.id} b={b} st={s.blocks.find((x) => x.id === b.id)} kind={spec.kind} path={spec.path} claims={spec.claims}
                     sel={sel?.kind === "block" && sel.id === b.id} onClick={() => pick({ kind: "block", id: b.id })} />
        );
      })}
      <g className="tm-edges tm-edges-done">
        {geo.edges.filter((e) => e.kind === "done").map((e) => <EdgeView key={e.key} e={e} lit={litOf(e, byId, s)} />)}
      </g>
    </svg>
  );
}

function fit(geo: { width: number; height: number }, room: { w: number; h: number }): number {
  if (!room.w || !room.h) return 1;
  return Math.max(MIN_SCALE, Math.min(1, (room.w - 4) / geo.width, (room.h - 4) / geo.height));
}

/** The scroll box's size, kept up to date. */
function useRoom(box: React.RefObject<HTMLDivElement | null>): { w: number; h: number } {
  const [room, setRoom] = useState({ w: 0, h: 0 });
  useEffect(() => {
    const el = box.current;
    if (!el) return;
    const read = () => setRoom((r) => (r.w === el.clientWidth && r.h === el.clientHeight ? r : { w: el.clientWidth, h: el.clientHeight }));
    read();
    const ro = new ResizeObserver(read);
    ro.observe(el);
    return () => ro.disconnect();
  });
  return room;
}

export function BoardDetail() {
  const loaded = useTeam((s) => s.loaded);
  const error = useTeam((s) => s.error);
  const has = useTeam((s) => !!s.info?.team);
  const box = useRef<HTMLDivElement>(null);
  const room = useRoom(box);
  if (!loaded) return <div className="og-wait mono muted">reading the team...</div>;
  if (!has) return <Empty title="No team to draw" body={error || "The Start view makes the team file; Validate lists what is wrong with one."} />;
  return (
    <div className="tm" data-testid="team-board-body">
      <RunBar />
      <div className="tm-scroll" ref={box}>
        <TeamBoard room={room} />
      </div>
      <div className="tm-legend mono muted">
        <span><i className="tm-key tm-key-done" /> stage_done</span>
        <span><i className="tm-key tm-key-reads" /> reads</span>
        <span><i className="tm-key tm-key-writes" /> writes</span>
        <span><i className="tm-key tm-key-change" /> block_change</span>
        <span>click a member, a stage or a block</span>
      </div>
    </div>
  );
}

export function BoardGlance() {
  const n = useTeam((s) => s.info?.team?.members.length || 0);
  const st = useTeam((s) => s.info?.team?.workflow.stages.length || 0);
  const running = useTeam(runningCount);
  const gated = useTeam((s) => gatedRows(s).length);
  const kicker = useTeam((s) => (s.board?.run ? `RUN ${s.board.state.toUpperCase()}` : "NO RUN YET"));
  return (
    <div className="glance">
      <div className="glance-kicker mono">{kicker}</div>
      <div className="glance-numbers">
        <Metric value={n} label="members" />
        <Metric value={st} label="stages" />
        <Metric value={running} label="running" tone={running ? "accent" : undefined} />
        <Metric value={gated} label="at a gate" tone={gated ? "warn" : undefined} />
      </div>
      <div className="glance-hint">Expand for the board: members as columns, stages as boxes.</div>
    </div>
  );
}

export function useBoardMotion(): MotionState {
  const r = useTeam((s) => s.board?.stages || NONE);
  if (r.some((x) => x.state === "failed")) return "error";
  if (r.some((x) => x.state === "gated")) return "waiting";
  if (r.some((x) => x.state === "running")) return "working";
  return r.length ? "idle" : "none";
}
