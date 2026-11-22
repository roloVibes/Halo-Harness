// A session's map, lit (3.6.0.0 R4; 3.6.0.2 R7 R10): what Session's Live drawer (routes/session/MapDown.tsx) and Agents'
// Live view share -- the map the session runs on (read by version, mapFiles.ts), each box's state and what it does now from the
// overlay (overlay.ts), its children as rows inside their box and a workflow as its block (litView.ts withRun, RunRows.tsx;
// 3.6.0.2 R14 R15), the hand-offs counted and in flight (overlayHops.ts; R16 R49) -- and a box's face: its name, then
// "kind · state", whole (no cap, no ellipsis: the box grows to hold it, R10). The frame (scroll, zoom, rows, the "↓" slot)
// is the drawing's own; its clock ticks only while `shown` (runParts.tsx). 3.6.0.0 R5: a session that did not start on a map is drawn as main and the helpers it started.
import { useContext, useEffect, useMemo, useRef } from "react";
import { useStore } from "../../../lib/store";
import { useSessionRecord, type RecordAgent } from "../../../lib/work/record";
import { useNow } from "../../fleet/store";
import { MAIN_HOLD } from "./groupWords";
import { STATE_WORDS } from "./LitBits";
import { lit, ownsMap, startLit, type LitSession } from "./litStore";
import { autoView, withRun } from "./litView";
import { autoGroups, type AutoGroup, type GRow } from "./overlayGroups";
import { useMapFile, type Got } from "./mapFiles";
import type { DrawBox, MapDetail } from "./mapTypes";
import { overlay, type BoxState, type Overlay } from "./overlay";
import { groupLive, groupTotals, inFlight, NO_TOTALS, type Totals } from "./overlayHops";
import { BlockFace, KidRows, NewTag } from "./RunRows";
import { NO_NOW, nowWords } from "./nowLine";
import { heldRows, nowFit, type Kept } from "./nowRoom";
import { RunCtx, ToolClock, useNowOf } from "./runParts";
import { turnLine, turnRows } from "./turnWords";
import { view, type MapView } from "./view";

const NO_AGENTS: RecordAgent[] = [];
const NO_MAP = { map: { format: "map/1", name: "", boxes: [], lines: [] }, scope: "starter", writable: false, in_use: false,
  problems: [], boxes: {}, main: { agent: "main" } } as unknown as MapDetail;

/** `totals`: the session's hand-offs counted (R49); `live`: the lines with a hand-off in flight now (R16). */
export type Lit = { detail: MapDetail | null; ov: Overlay | null; v: MapView; totals: Totals; live: Set<string>; agents: RecordAgent[];
  /** 3.6.0.2 R28: the read (removed / unreadable), and `unlit`: a map drawn calm (Just built, R30) */
  got?: Got | null; unlit?: boolean; /** the drawing's clock, seconds (P4 batch 13) */ now?: number;
  /** 3.6.0.5 B1: on Auto (the row says `map_plain`) the groups drawn, else undefined; B30 the row's `map_agents` */
  groups?: AutoGroup[]; mapAgents?: string[];
  /** 3.6.0.13 L3: the kinds main was told it can start (null before its first request): main's hover */ told?: LitSession["told"] };

/** R49: what the drawing's layout depends on -- the blocks (workflow, caller, step count) and which box holds which
 *  rows -- never a frame's state or time, so the layout is computed again only when that changes. */
const shapeOf = (ov: Overlay | null, groups?: AutoGroup[]): string => !ov ? "" : JSON.stringify([
  Object.entries(ov.blocks).map(([w, b]) => [w, b.box, b.caller, b.steps.length, b.off]),
  Object.entries(ov.kids).map(([box, ks]) => [box, ks.map((k) => k.aid)]),
  (groups || []).map((g) => [g.n, g.members.map((m) => m.aid)]), // 3.6.0.5: a member joining re-lays out once (R12 holds it)
]);

/** The session's map (null while it is read, or gone: `got` says which), its overlay and the lit view (boxes, strip,
 *  lines). `show`: another map to draw for this session (3.6.0.2 R30 Just built), `unlit`: drawn calm, no overlay. The
 *  file is read by version (mapFiles.ts, R27 R28 R50): after the first draw, softly, by the row's scope and path. */
export function useLit(s: LitSession, show?: { map: string; unlit?: boolean }, shown = true): Lit {
  useEffect(() => startLit(), []);
  const name = show ? show.map : s.map || "";
  const own = ownsMap(s.map, show);
  const got = useMapFile(name, own ? { scope: s.scope, path: s.path } : {}, !!name);
  const detail = !name ? NO_MAP : got && "detail" in got ? got.detail : null;
  const unlit = !!show?.unlit;
  const rec = useSessionRecord(s.sid);
  const evs = useStore(lit, (x) => x.events[s.sid]);
  const events = unlit ? undefined : evs;
  const now = useNow(shown, 1000) / 1000; // P4 batch 13: the drawing's one clock, stopped while it is not on screen
  const tot = useStore(lit, (x) => x.totals[s.sid]) || NO_TOTALS;
  const totals = unlit ? NO_TOTALS : tot;
  const rows = useMemo(() => (unlit ? [] : (rec?.agents || []).map((a) => ({ ...a.row, agent_id: a.id, ended: a.ended }) as GRow)), [rec, unlit]);
  const auto = !!s.auto && !show; // 3.6.0.5 B1: groups only on a row that says map_plain, never on another map shown
  const plain = s.plain !== false;
  // R30: Just built is drawn calm: no overlay (main reads idle, not "working", on a map the session does not run on)
  const ov = useMemo(() => (detail && !unlit ? overlay(detail.map, rows, events || [], now, { plain }) : null), [detail, rows, events, now, plain, unlit]);
  const groups = useMemo(() => (auto && ov ? autoGroups(rows, ov.blocks) : undefined), [auto, rows, ov]);
  const shape = shapeOf(ov, groups);
  const ovNow = useRef(ov), groupsNow = useRef(groups);
  ovNow.current = ov;
  groupsNow.current = groups;
  const v = useMemo(() => (groupsNow.current ? autoView(view(detail?.map || null, [], []), groupsNow.current)
    : withRun(view(detail?.map || null, [], []), ovNow.current, detail, plain)), [detail, shape, plain]); // eslint-disable-line react-hooks/exhaustive-deps
  // B12a: on Auto main's line into a group is counted and lit from the group's rows, never from a map_hop frame
  const shownTotals = useMemo(() => (groups ? groupTotals(groups) : totals), [groups, totals]);
  const live = useMemo(() => (groups ? groupLive(groups) : inFlight(totals, rows, !unlit && !!s.busy)), [groups, totals, rows, s.busy, unlit]);
  return { detail, ov, v, totals: shownTotals, live, agents: unlit ? NO_AGENTS : rec?.agents || NO_AGENTS, got, unlit, now, groups,
           mapAgents: s.map_agents || [], told: s.told ?? null };
}

/** A box's state and, for a made-up helper, its agent id. */
export function litState(b: DrawBox, ov: Overlay | null): { st: BoxState; helper?: string } {
  const h = b.helper ? ov?.helpers.find((x) => x.aid === b.helper) : undefined;
  return { st: h?.state || ov?.boxes[b.id]?.state || "idle", helper: h?.aid };
}

/** A box's face: the name (13.5 px), then "kind · state" (12 px) and, while it works, what it does now -- every word; then
 *  its children as rows (R15). A workflow's box is its block (R14). */
export function LitFace({ b, ov, sid, tag, bare, main, w = 248 }: { b: DrawBox; ov: Overlay | null; sid: string; tag?: string;
  /** 3.6.0.5 B1: on Auto main's children are its groups' members, never rows in main's box */ bare?: boolean;
  /** 3.6.0.13 L2a: main's record agent on Auto (its NOW) and the box's width (`w`, NOW's room) */ main?: RecordAgent; w?: number }) {
  if (b.block) return <BlockFace block={b.block} ov={ov} tag={tag} />;
  const { st } = litState(b, ov);
  const doing = st === "working" ? ov?.boxes[b.id]?.doing : "";
  // k/batch02 entry 1: on Auto main's rows that come and go with its state keep their room (a hidden twin of the fullest)
  const held = bare && b.main;
  const on = (st === "working" || st === "waiting") && !b.helper;
  const rows = (<>
    <span className="mp-lit-row mono" data-state={st}>{b.main ? "main" : b.kind} · {STATE_WORDS[st]}{doing ? ` · ${doing}` : ""}</span>
    {held ? <MainNow main={main} on={on} width={w - 24} /> : <ToolClock aids={b.main ? ["main"] : ov?.boxes[b.id]?.agents || []} on={on} />}
  </>);
  return (
    <span className="mp-inner">
      <b className="mp-name">{b.name}</b>
      {tag && <NewTag text={tag} />}
      {held ? (
        <span className="mp-hold">
          <span className="mp-hold-now">{rows}</span>
          <span className="mp-hold-twin mono" aria-hidden="true">
            <span className="mp-hold-row" data-text={MAIN_HOLD.row} />
            <span className="mp-hold-row" data-text={MAIN_HOLD.clock} data-secs={MAIN_HOLD.secs} />
          </span>
        </span>
      ) : rows}
      {held && <MainTurn main={main} width={w - 24} />}
      <KidRows kids={bare ? [] : ov?.kids[b.id] || []} sid={sid} sender={b.id} />
    </span>
  );
}

/** 3.6.0.13 L2a, L2b with R6: main's NOW on Auto, in the tool clock's place -- drawn while main's box works or waits, else
 *  the blank kept line; two rows held from the first draw, one growth when the drawing is not held (else "a tool · {s}"),
 *  kept for the session's life. `width`: its text room (the box less its padding and border, 24). */
function MainNow({ main, on, width }: { main?: RecordAgent; on: boolean; width: number }) {
  const nw = useNowOf("main", main?.state || "", main?.started || 0, main?.ended || 0); // a null end: L1's end not seen
  const held = !!useContext(RunCtx)?.held;
  const kept = useRef<Kept>({ rows: heldRows(width), grown: false });
  const now = on ? nw : NO_NOW;
  const fit = nowFit(now, width, kept.current, held);
  kept.current = fit.kept;
  const cut = fit.text !== now.text; // the held form stands in for the words: only then they are this row's own tooltip
  return (
    <span className="mp-main-now mono" data-testid="map-main-now" data-now={now.kind} title={cut ? nowWords(now) : undefined}
          data-hover-skip={cut ? "" : undefined} style={{ minHeight: fit.rows * 17 }}>
      {fit.text}{fit.secs && <span className="mp-clock-secs">{fit.secs}</span>}
    </span>
  );
}

/** 3.6.0.13 L3 with R5: TURN under main's NOW on Auto, from main's row `turn` (3.6.0.10 M10): blank before the first turn,
 *  kept until his next message; 12/17 mono, the rows of its longest usual words held from the first draw; drawn under
 *  the held rows (`mp-hold`), never inside them, so the twin keeps holding the rows that come and go. */
function MainTurn({ main, width }: { main?: RecordAgent; width: number }) {
  return (
    <span className="mp-main-turn mono" data-testid="map-main-turn" style={{ minHeight: turnRows(width) * 17 }}>
      {turnLine(main?.row?.turn)}
    </span>
  );
}
