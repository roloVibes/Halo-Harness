// The Map's notice row (3.6.0.2 R55, R33): reserved from the first draw for the longest line it can be asked to hold
// with the names it has (a hidden twin, measured), so neither the quiet line (L1-L3, mapQuiet.ts) nor a build's notice
// (L4, mapSwitch.ts) ever moves the drawing under it. The notice replaces the quiet line while shown. Never amber.
import { useLayoutEffect, useMemo, useRef, useState } from "react";
import { Button } from "../../../lib/ui";
import { openMap, useMap } from "./mapStore";
import { quietRoom, useQuiet } from "./mapQuiet";
import { useMapBuilt, watchLive } from "./mapSwitch";
import { mapLine, type Line } from "./truth";

const NONE: never[] = [];

function Said({ line, testid, button, onPress }: { line: Line; testid: string; button: string; onPress: () => void }) {
  return (
    <p className="cw-line mp-quiet" data-testid={testid}>
      {line.text} <Button size="sm" onClick={onPress} data-testid={button}>{line.label}</Button>
    </p>
  );
}

export function NoticeRow() {
  const q = useQuiet(), on = q.on;
  const notice = useMapBuilt((s) => s.notice);
  const rows = useMap((s) => s.rows) || NONE;
  const file = useMap((s) => s.detail?.map || null);
  const room = useMemo(() => quietRoom(on, (file?.boxes || []).map((b) => b.workflow || "").filter(Boolean), rows.map((r) => r.name)), [on, file, rows]);
  const key = room.map((l) => l.text).join("|");
  const row = useRef<HTMLDivElement>(null), twin = useRef<HTMLDivElement>(null);
  const [minH, setMinH] = useState(0);
  const [w, setW] = useState(0);
  useLayoutEffect(() => {
    const el = row.current;
    if (!el || typeof ResizeObserver === "undefined") return;
    const ro = new ResizeObserver(() => setW(Math.round(el.clientWidth)));
    ro.observe(el);
    return () => ro.disconnect();
  }, []);
  useLayoutEffect(() => { // measured when the names or the width change, never because a line came or went
    const kids = [...(twin.current?.children || [])] as HTMLElement[];
    const h = Math.max(0, ...kids.map((k) => k.offsetHeight));
    if (h && Math.abs(h - minH) > 0.5) setMinH(h);
  }, [key, w]); // eslint-disable-line react-hooks/exhaustive-deps
  const l4 = notice ? mapLine({ kind: "L4", ...notice })[0] : null;
  const quiet = q.facts ? mapLine(q.facts)[0] : null;
  return (
    <div className="mp-notice-row" ref={row} data-testid="map-notice-row" style={minH ? { minHeight: minH } : undefined}>
      {l4 ? <Said line={l4} testid="map-built-notice" button="map-built-open" onPress={() => void openMap(notice!.map)} />
        : quiet ? <Said line={quiet} testid="map-quiet" button="map-watch-live" onPress={() => watchLive(q.sid)} /> : null}
      <div className="mp-notice-twin" ref={twin} aria-hidden="true">
        {room.map((l, i) => <p key={i} className="cw-line mp-quiet">{l.text} <button type="button" tabIndex={-1} className="btn btn-default btn-sm"><span className="btn-label">{l.label}</span></button></p>)}
      </div>
    </div>
  );
}
