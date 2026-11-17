// A session's map, lit (3.6.0.0 R4; 3.6.0.2 R7 R10): what Session's Live drawer (routes/session/MapDown.tsx) and Agents'
// Live view share -- the map the session runs on (read once per name), each box's state and what it does now from the
// overlay (overlay.ts), its children as rows inside their box and a workflow as its block (litView.ts withRun, RunRows.tsx;
// 3.6.0.2 R14 R15), the hand-offs counted and in flight (overlayHops.ts; R16 R49) -- and a box's face: its name, then
// "kind · state", whole (no cap, no ellipsis: the box grows to hold it, R10). The frame (scroll, zoom, rows, the "↓" slot)
// is the drawing's own. 3.6.0.0 R5: a session that did not start on a map is drawn as main and the helpers it started.
import { useEffect, useMemo, useRef, useState } from "react";
import { api } from "../../../lib/api";
import { useStore } from "../../../lib/store";
import { useSessionRecord, type RecordAgent } from "../../../lib/work/record";
import { useNow } from "../../fleet/store";
import { STATE_WORDS } from "./LitBits";
import { lit, startLit, type LitSession } from "./litStore";
import { withRun } from "./litView";
import type { DrawBox, MapDetail } from "./mapTypes";
import { overlay, type BoxState, type Overlay, type OvRow } from "./overlay";
import { inFlight, NO_TOTALS, type Totals } from "./overlayHops";
import { BlockFace, KidRows } from "./RunRows";
import { view, type MapView } from "./view";

const files = new Map<string, MapDetail>();
const NO_AGENTS: RecordAgent[] = [];
const NO_MAP = { map: { format: "map/1", name: "", boxes: [], lines: [] }, scope: "starter", writable: false, in_use: false,
  problems: [], boxes: {}, main: { agent: "main" } } as unknown as MapDetail;

/** `totals`: the session's hand-offs counted (R49); `live`: the lines with a hand-off in flight now (R16). */
export type Lit = { detail: MapDetail | null; ov: Overlay | null; v: MapView; totals: Totals; live: Set<string>; agents: RecordAgent[] };

/** R49: what the drawing's layout depends on -- the blocks (workflow, caller, step count) and which box holds which
 *  rows -- never a frame's state or time, so the layout is computed again only when that changes. */
const shapeOf = (ov: Overlay | null): string => !ov ? "" : JSON.stringify([
  Object.entries(ov.blocks).map(([w, b]) => [w, b.box, b.caller, b.steps.length, b.off]),
  Object.entries(ov.kids).map(([box, ks]) => [box, ks.map((k) => k.aid)]),
]);

/** The session's map (null while it is read), its overlay and the lit view (boxes, strip, lines). */
export function useLit(s: LitSession): Lit {
  useEffect(() => startLit(), []);
  const [detail, setDetail] = useState<MapDetail | null>(() => (s.map ? files.get(s.map) || null : NO_MAP));
  useEffect(() => {
    if (!s.map) return setDetail(NO_MAP);
    void api.get<MapDetail>(`crew/map/${s.map}`).then((d) => (files.set(s.map!, d), setDetail(d))).catch(() => setDetail(null));
  }, [s.map]);
  const rec = useSessionRecord(s.sid);
  const events = useStore(lit, (x) => x.events[s.sid]);
  const now = useNow(true, 1000) / 1000;
  const totals = useStore(lit, (x) => x.totals[s.sid]) || NO_TOTALS;
  const rows = useMemo(() => (rec?.agents || []).map((a) => ({ ...a.row, agent_id: a.id }) as OvRow), [rec]);
  const plain = s.plain !== false;
  const ov = useMemo(() => (detail ? overlay(detail.map, rows, events || [], now, { plain }) : null), [detail, rows, events, now, plain]);
  const shape = shapeOf(ov);
  const ovNow = useRef(ov);
  ovNow.current = ov;
  const v = useMemo(() => withRun(view(detail?.map || null, [], []), ovNow.current, detail, plain), [detail, shape, plain]); // eslint-disable-line react-hooks/exhaustive-deps
  const live = useMemo(() => inFlight(totals, rows, !!s.busy), [totals, rows, s.busy]);
  return { detail, ov, v, totals, live, agents: rec?.agents || NO_AGENTS };
}

/** A box's state and, for a made-up helper, its agent id. */
export function litState(b: DrawBox, ov: Overlay | null): { st: BoxState; helper?: string } {
  const h = b.helper ? ov?.helpers.find((x) => x.aid === b.helper) : undefined;
  return { st: h?.state || ov?.boxes[b.id]?.state || "idle", helper: h?.aid };
}

/** A box's face: the name (13.5 px), then "kind · state" (12 px) and, while it works, what it does now -- every word; then
 *  its children as rows (R15). A workflow's box is its block (R14). */
export function LitFace({ b, ov, sid }: { b: DrawBox; ov: Overlay | null; sid: string }) {
  if (b.block) return <BlockFace block={b.block} ov={ov} />;
  const { st } = litState(b, ov);
  const doing = st === "working" ? ov?.boxes[b.id]?.doing : "";
  return (
    <span className="mp-inner">
      <b className="mp-name">{b.name}</b>
      <span className="mp-lit-row mono" data-state={st}>{b.main ? "main" : b.kind} · {STATE_WORDS[st]}{doing ? ` · ${doing}` : ""}</span>
      <KidRows kids={ov?.kids[b.id] || []} sid={sid} sender={b.id} />
    </span>
  );
}
