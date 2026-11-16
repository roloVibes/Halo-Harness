// A session's map, lit (3.6.0.0 R4; 3.6.0.2 R7 R10): what Session's Live drawer (routes/session/MapDown.tsx) and Agents'
// Live view share -- the map the session runs on (read once per name), each box's state and what it does now from the
// overlay (overlay.ts), the helpers it made up beside their box (litView.ts) -- and a box's face: its name, then
// "kind · state", whole (no cap, no ellipsis: the box grows to hold it, R10). The frame (scroll, zoom, rows, the "↓" slot)
// is the drawing's own. 3.6.0.0 R5: a session that did not start on a map is drawn as main and the helpers it started.
import { useEffect, useMemo, useState } from "react";
import { api } from "../../../lib/api";
import { useStore } from "../../../lib/store";
import { useSessionRecord } from "../../../lib/work/record";
import { useNow } from "../../fleet/store";
import { STATE_WORDS } from "./LitBits";
import { lit, startLit, type LitSession } from "./litStore";
import { withLit } from "./litView";
import type { DrawBox, MapDetail } from "./mapTypes";
import { overlay, type BoxState, type Overlay, type OvRow } from "./overlay";
import { view, type MapView } from "./view";

const files = new Map<string, MapDetail>();
const NO_MAP = { map: { format: "map/1", name: "", boxes: [], lines: [] }, scope: "starter", writable: false, in_use: false,
  problems: [], boxes: {}, main: { agent: "main" } } as unknown as MapDetail;

export type Lit = { detail: MapDetail | null; ov: Overlay | null; v: MapView };

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
  const ov = useMemo(() => (detail ? overlay(detail.map, (rec?.agents || []).map((a) => ({ ...a.row, agent_id: a.id }) as OvRow), events || [], now) : null),
    [detail, rec, events, now]);
  const v = useMemo(() => withLit(view(detail?.map || null, [], []), ov), [detail, ov]);
  return { detail, ov, v };
}

/** A box's state and, for a made-up helper, its agent id. */
export function litState(b: DrawBox, ov: Overlay | null): { st: BoxState; helper?: string } {
  const h = b.helper ? ov?.helpers.find((x) => x.aid === b.helper) : undefined;
  return { st: h?.state || ov?.boxes[b.id]?.state || "idle", helper: h?.aid };
}

/** A box's face: the name (13.5 px), then "kind · state" (12 px) and, while it works, what it does now -- every word. */
export function LitFace({ b, ov }: { b: DrawBox; ov: Overlay | null }) {
  const { st, helper } = litState(b, ov);
  const kind = b.main ? "main" : helper ? "helper" : b.kind;
  const doing = !helper && st === "working" ? ov?.boxes[b.id]?.doing : "";
  return (
    <span className="mp-inner">
      <b className="mp-name">{b.name}</b>
      <span className="mp-lit-row mono" data-state={st}>{kind} · {STATE_WORDS[st]}{doing ? ` · ${doing}` : ""}</span>
      {helper && <span className="mp-lit-row mp-made">made up for this task</span>}
    </span>
  );
}
