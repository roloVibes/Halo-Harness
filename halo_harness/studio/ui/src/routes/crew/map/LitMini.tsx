// A session's map, lit (3.6.0.0 R4; 3.6.0.2 R7 R10): what Session's Live drawer (routes/session/MapDown.tsx) and Agents'
// Live view share -- the map the session runs on (read by version, mapFiles.ts), each box's state and what it does now from the
// overlay (overlay.ts), its children as rows inside their box and a workflow as its block (litView.ts withRun, RunRows.tsx;
// 3.6.0.2 R14 R15), the hand-offs counted and in flight (overlayHops.ts; R16 R49) -- and a box's face: its name, then
// "kind · state", whole (no cap, no ellipsis: the box grows to hold it, R10). The frame (scroll, zoom, rows, the "↓" slot)
// is the drawing's own; its clock ticks only while `shown` (runParts.tsx). 3.6.0.0 R5: a session that did not start on a map is drawn as main and the helpers it started.
import { useEffect, useMemo, useRef } from "react";
import { useStore } from "../../../lib/store";
import { useSessionRecord, type RecordAgent } from "../../../lib/work/record";
import { useNow } from "../../fleet/store";
import { STATE_WORDS } from "./LitBits";
import { lit, startLit, type LitSession } from "./litStore";
import { withRun } from "./litView";
import { useMapFile, type Got } from "./mapFiles";
import type { DrawBox, MapDetail } from "./mapTypes";
import { overlay, type BoxState, type Overlay, type OvRow } from "./overlay";
import { inFlight, NO_TOTALS, type Totals } from "./overlayHops";
import { BlockFace, KidRows, NewTag } from "./RunRows";
import { ToolClock } from "./runParts";
import { view, type MapView } from "./view";

const NO_AGENTS: RecordAgent[] = [];
const NO_MAP = { map: { format: "map/1", name: "", boxes: [], lines: [] }, scope: "starter", writable: false, in_use: false,
  problems: [], boxes: {}, main: { agent: "main" } } as unknown as MapDetail;

/** `totals`: the session's hand-offs counted (R49); `live`: the lines with a hand-off in flight now (R16). */
export type Lit = { detail: MapDetail | null; ov: Overlay | null; v: MapView; totals: Totals; live: Set<string>; agents: RecordAgent[];
  /** 3.6.0.2 R28: the read (removed / unreadable), and `unlit`: a map drawn calm (Just built, R30) */
  got?: Got | null; unlit?: boolean; /** the drawing's clock, seconds (P4 batch 13) */ now?: number };

/** R49: what the drawing's layout depends on -- the blocks (workflow, caller, step count) and which box holds which
 *  rows -- never a frame's state or time, so the layout is computed again only when that changes. */
const shapeOf = (ov: Overlay | null): string => !ov ? "" : JSON.stringify([
  Object.entries(ov.blocks).map(([w, b]) => [w, b.box, b.caller, b.steps.length, b.off]),
  Object.entries(ov.kids).map(([box, ks]) => [box, ks.map((k) => k.aid)]),
]);

/** The session's map (null while it is read, or gone: `got` says which), its overlay and the lit view (boxes, strip,
 *  lines). `show`: another map to draw for this session (3.6.0.2 R30 Just built), `unlit`: drawn calm, no overlay. The
 *  file is read by version (mapFiles.ts, R27 R28 R50): after the first draw, softly, by the row's scope and path. */
export function useLit(s: LitSession, show?: { map: string; unlit?: boolean }, shown = true): Lit {
  useEffect(() => startLit(), []);
  const name = show ? show.map : s.map || "";
  const own = !show || show.map === s.map;
  const got = useMapFile(name, own ? { scope: s.scope, path: s.path } : {}, !!name);
  const detail = !name ? NO_MAP : got && "detail" in got ? got.detail : null;
  const unlit = !!show?.unlit;
  const rec = useSessionRecord(s.sid);
  const evs = useStore(lit, (x) => x.events[s.sid]);
  const events = unlit ? undefined : evs;
  const now = useNow(shown, 1000) / 1000; // P4 batch 13: the drawing's one clock, stopped while it is not on screen
  const tot = useStore(lit, (x) => x.totals[s.sid]) || NO_TOTALS;
  const totals = unlit ? NO_TOTALS : tot;
  const rows = useMemo(() => (unlit ? [] : (rec?.agents || []).map((a) => ({ ...a.row, agent_id: a.id }) as OvRow)), [rec, unlit]);
  const plain = s.plain !== false;
  // R30: Just built is drawn calm: no overlay (main reads idle, not "working", on a map the session does not run on)
  const ov = useMemo(() => (detail && !unlit ? overlay(detail.map, rows, events || [], now, { plain }) : null), [detail, rows, events, now, plain, unlit]);
  const shape = shapeOf(ov);
  const ovNow = useRef(ov);
  ovNow.current = ov;
  const v = useMemo(() => withRun(view(detail?.map || null, [], []), ovNow.current, detail, plain), [detail, shape, plain]); // eslint-disable-line react-hooks/exhaustive-deps
  const live = useMemo(() => inFlight(totals, rows, !unlit && !!s.busy), [totals, rows, s.busy, unlit]);
  return { detail, ov, v, totals, live, agents: unlit ? NO_AGENTS : rec?.agents || NO_AGENTS, got, unlit, now };
}

/** A box's state and, for a made-up helper, its agent id. */
export function litState(b: DrawBox, ov: Overlay | null): { st: BoxState; helper?: string } {
  const h = b.helper ? ov?.helpers.find((x) => x.aid === b.helper) : undefined;
  return { st: h?.state || ov?.boxes[b.id]?.state || "idle", helper: h?.aid };
}

/** A box's face: the name (13.5 px), then "kind · state" (12 px) and, while it works, what it does now -- every word; then
 *  its children as rows (R15). A workflow's box is its block (R14). */
export function LitFace({ b, ov, sid, tag }: { b: DrawBox; ov: Overlay | null; sid: string; tag?: string }) {
  if (b.block) return <BlockFace block={b.block} ov={ov} tag={tag} />;
  const { st } = litState(b, ov);
  const doing = st === "working" ? ov?.boxes[b.id]?.doing : "";
  return (
    <span className="mp-inner">
      <b className="mp-name">{b.name}</b>
      {tag && <NewTag text={tag} />}
      <span className="mp-lit-row mono" data-state={st}>{b.main ? "main" : b.kind} · {STATE_WORDS[st]}{doing ? ` · ${doing}` : ""}</span>
      <ToolClock aids={b.main ? ["main"] : ov?.boxes[b.id]?.agents || []} on={st === "working" && !b.helper} />
      <KidRows kids={ov?.kids[b.id] || []} sid={sid} sender={b.id} />
    </span>
  );
}
