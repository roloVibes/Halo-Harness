// Session's Map panel, lit (3.6.0.0 R4, the brief's point 11): the same lit map as Agents -> 3 · Map, compact and
// read-only -- the map the running session started with, its boxes and lines laid out as on the tab (layout.ts), each
// box's state and what it does now from the same overlay (overlay.ts), the helpers it made up beside their box -- with
// a link to the Map tab. No dot, no label card, nothing to drag. A session that did not start on a map keeps the tree
// Session's Map drew before (routes/roles/LiveMap.tsx) until every session runs on a map (the next round).
import { useEffect, useLayoutEffect, useMemo, useRef, useState } from "react";
import { api } from "../../../lib/api";
import { useStore } from "../../../lib/store";
import { useSessionRecord } from "../../../lib/work/record";
import { setAgentsView } from "../../agents/store";
import { goSection } from "../../../lib/store";
import { useNow } from "../../fleet/store";
import { STATE_WORDS } from "./LitBits";
import { lit, startLit, type LitSession } from "./litStore";
import { withLit } from "./litView";
import { BOX_W, estimate, layout } from "./layout";
import { openMap } from "./mapStore";
import type { MapDetail } from "./mapTypes";
import { overlay, type OvRow } from "./overlay";
import { view } from "./view";

const files = new Map<string, MapDetail>();

export function LitMini({ s }: { s: LitSession }) {
  useEffect(() => startLit(), []);
  const [detail, setDetail] = useState<MapDetail | null>(() => files.get(s.map || "") || null);
  useEffect(() => {
    if (!s.map) return;
    void api.get<MapDetail>(`crew/map/${s.map}`).then((d) => (files.set(s.map!, d), setDetail(d))).catch(() => setDetail(null));
  }, [s.map]);
  const rec = useSessionRecord(s.sid);
  const events = useStore(lit, (x) => x.events[s.sid]);
  const now = useNow(true, 1000) / 1000;
  const ov = useMemo(() => (detail ? overlay(detail.map, (rec?.agents || []).map((a) => ({ ...a.row, agent_id: a.id }) as OvRow), events || [], now) : null),
    [detail, rec, events, now]);
  const v = useMemo(() => withLit(view(detail?.map || null, [], []), ov), [detail, ov]);
  const g = layout(v.boxes, v.lines, (b) => estimate(b, false, 0) + 20);
  const box = useRef<HTMLDivElement>(null);
  const [k, setK] = useState(1);
  useLayoutEffect(() => { // fitted to the panel's width (no sideways scroll), never under 60 %: past that it scrolls down
    const w = box.current?.clientWidth || 0;
    const want = w && g.w ? Math.max(0.6, Math.min(1, (w - 4) / g.w)) : 1;
    if (Math.abs(want - k) > 0.01) setK(want);
  });
  const open = () => { setAgentsView("map"); goSection("agents", "map"); void openMap(s.map || ""); };
  if (!detail) return <p className="cw-line" data-testid="session-lit-map-reading">Reading the map {s.map}...</p>;
  return (
    <div className="mp-mini" data-testid="session-lit-map" data-map={s.map || ""} data-sid={s.sid}>
      <div className="mp-mini-head">
        <span className="cw-line">A session is running on the map {s.map}.</span>
        <button type="button" className="mp-link" onClick={open} data-testid="session-lit-open">Open it on the Map tab</button>
      </div>
      <div className="mp-mini-scroll" ref={box}>
        <div className="mp-mini-size" style={{ width: g.w * k, height: g.h * k }}>
        <div className="mp-mini-world" style={{ width: g.w, height: g.h, transform: `scale(${k})` }}>
          <svg className="mp-lines" width={g.w} height={g.h} aria-hidden="true">
            {g.lines.map((l) => <path key={l.key} d={l.d} className="mp-line" data-helper={l.helper || undefined}
                                      data-pulse={ov?.pulses.some((p) => p.from === l.from && p.to === l.to) ? "1" : undefined} />)}
          </svg>
          {g.boxes.map((b) => {
            const h = b.helper ? ov?.helpers.find((x) => x.aid === b.helper) : undefined;
            const st = h?.state || ov?.boxes[b.id]?.state || "idle";
            return (
              <div key={b.id} className="mp-box" data-lit="live" data-state={st} data-helper={h ? h.aid : undefined} data-testid="session-lit-box" data-box={b.id}
                   style={{ position: "absolute", left: b.x, top: b.y, width: BOX_W, minHeight: b.h }} title={`${b.name}: ${STATE_WORDS[st]}`}>
                <span className="mp-kind mono">{b.main ? "main" : h ? "helper" : b.kind}</span>
                <b className="mp-name">{b.name}</b>
                <span className="mp-lit-row mono" data-state={st}>{STATE_WORDS[st]}{!h && ov?.boxes[b.id] && st === "working" ? ` · ${ov.boxes[b.id].doing}` : ""}</span>
                {h && <span className="mp-tag mp-made">made up for this task</span>}
              </div>
            );
          })}
        </div>
        </div>
      </div>
    </div>
  );
}
