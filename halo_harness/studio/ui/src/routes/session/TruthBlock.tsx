// The truth block over Session's Live drawing (3.6.0.2 R20 R21 R22 R23, section 4): which map the chosen session runs on
// and since when, S13 with [New session] when new sessions run on another map, T7 first while it runs a workflow that is
// a box on that map, T5 when its map changed; under it the status line. Every sentence is truth.ts's (TruthBlock builds
// none). R20: its height is reserved from the first draw for the longest state truth.ts gives for this session's REAL
// names (a hidden twin of `reserve`, measured at the block's width, never clamped; nothing held for a name it does not
// have: P4 batch 11), so the drawing below never moves when a fact changes; a name that really changes (a switch of the
// map new sessions use, a workflow that starts) is measured again, once. The status line's room is its own twin's. Never amber. [New session] opens the New session form in the drawer's corner (R5: the form
// starts a session, never this button).
import { useEffect, useLayoutEffect, useMemo, useRef, useState } from "react";
import { api } from "../../lib/api";
import { useStore } from "../../lib/store";
import { useSessionRecord } from "../../lib/work/record";
import { useBuilt } from "../crew/map/built";
import { lit, startLit } from "../crew/map/litStore";
import type { MapDetail } from "../crew/map/mapTypes";
import { nextMap, reserve, statusLine, statusRoom, truthLines, truthState, type Line, type TruthFacts } from "../crew/map/truth";
import { NewSession } from "./NewSession";
import { mapBody, noteBody, type MapBody } from "./pick";
import { knownFlows, nameOf, statusOf } from "./statusOf";

const LIVE = ["queued", "running", "paused", "waiting"];

/** {B}'s map body once a workflow runs: a builder_done frame's (pick.ts noteBuild), else the one read of it after the
 *  first draw (never a fetch before it; R22, R28); a read that failed is forgotten, so the next run reads again. */
function useBody(name: string, want: boolean): MapBody | null {
  const [, setN] = useState(0);
  useEffect(() => {
    if (!want || !name || mapBody(name) !== undefined) return;
    noteBody(name, false);
    void api.get<MapDetail>(`crew/map/${name}`).then((d) => (noteBody(name, d.map), setN((n) => n + 1)), () => noteBody(name, null));
  }, [name, want]);
  return (want && mapBody(name)) || null;
}

function Lines({ lines, onNew }: { lines: Line[]; onNew?: () => void }) {
  return (
    <>
      {lines.map((l, i) => (
        <p key={i} className="mp-truth-line">
          {l.text}
          {l.act === "new-session" && (
            <>
              {" "}
              <button type="button" className="mp-link mp-truth-new" data-testid={onNew ? "session-truth-new" : undefined}
                      tabIndex={onNew ? undefined : -1} onClick={onNew}>{l.label}</button>
            </>
          )}
        </p>
      ))}
    </>
  );
}

/** `f`: the session's facts (pick.ts factsOf), or `{ none: true, b }` for Empty; `sid`: the session ("" for Empty);
 *  `held`: Empty while {B} is not read yet (its room is kept, no words: never a {B} that may be false); `off`: the hand-offs
 *  outside the map (R17, the overlay's count by rows; 0 on the default map). */
export function TruthBlock({ f: given, sid, held, off = 0 }: { f: TruthFacts; sid: string; held?: boolean; off?: number }) {
  useEffect(() => startLit(), []);
  const rec = useSessionRecord(sid);
  const rows = (rec?.agents || []).map((a) => ({ ...a.row, agent_id: a.id }));
  const events = useStore(lit, (x) => (sid ? x.events[sid] : undefined)) || [];
  const flow = rows.find((r) => LIVE.includes(String(r.state || "")) && r.crew?.workflow)?.crew?.workflow || "";
  const B = nextMap(given.b);
  const body = useBody(B, !!flow && !given.none);
  const runs = !!flow && !!body && (body.boxes || []).some((b) => b?.workflow === flow);
  const moved = useBuilt((x) => (sid ? x.changed[sid] : undefined)); // 3.6.0.9 V: workflows changed by a plain write
  const flowsChanged = useMemo(() => Object.entries(moved || {}).map(([name, t]) => ({ name, t })), [moved]);
  const f: TruthFacts = { ...given, workflow: runs ? flow : null, flowsChanged }; // R22: T7 only once B's body says W is a box on it
  const lines = truthLines(f);
  const root = useRef<HTMLDivElement>(null), twin = useRef<HTMLDivElement>(null);
  const [w, setW] = useState(0);
  const [minH, setMinH] = useState(0);
  const most = useRef(0);
  useLayoutEffect(() => {
    const el = root.current;
    if (!el) return;
    const read = () => setW(el.clientWidth);
    read();
    const ro = new ResizeObserver(read);
    ro.observe(el);
    return () => ro.disconnect();
  }, []);
  const room = given.none ? lines : reserve(f, w || 408).lines;
  const names = `${f.a}|${f.bNone ? "" : nextMap(f.b)}|${f.workflow || ""}|${held ? "held" : ""}`, named = useRef(names);
  useLayoutEffect(() => { // R20: the reserve of the REAL names, measured; it only grows while they stay (P4 batch 11)
    const h = twin.current?.offsetHeight || 0;
    if (named.current !== names) (named.current = names, most.current = h, setMinH(h)); // a name changed: measured again, once
    else if (h > most.current + 0.5) (most.current = h, setMinH(h));
  });
  const busy = !!given.busy;
  const status = statusOf(rows, events, busy, off);
  // every sentence this run can show, each measured in the twin: a short one can wrap taller than a long one (P4 batch 12)
  const said = statusRoom(status, rows.map(nameOf), knownFlows(rows, events), !!given.plain || !given.a);
  const stwin = useRef<HTMLDivElement>(null), sMost = useRef(0);
  const [sMin, setSMin] = useState(0);
  useLayoutEffect(() => { // R23: the status line's room is the tallest sentence this run can show, from its first draw
    const h = Math.max(0, ...[...(stwin.current?.children || [])].map((el) => (el as HTMLElement).offsetHeight));
    if (h > sMost.current + 0.5) (sMost.current = h, setSMin(h));
  });
  const [form, setForm] = useState(false);
  const st = truthState(f);
  return ( // R23: the status line sits UNDER the block, outside it: the block's words change only with a fact (R20)
    <div className="mp-truth-box">
      <div className="mp-truth" ref={root} data-testid="session-truth" data-state={st}>
        <div className="mp-truth-lines" style={{ minHeight: minH || undefined }}>
          <div className={`cw-line mp-truth-said${held ? " mp-truth-held" : ""}`} data-testid="session-lit-line" data-state={st} data-sid={sid}>
            {!held && <Lines lines={lines} onNew={() => setForm(true)} />}
          </div>
          <div className="cw-line mp-truth-said mp-truth-twin" ref={twin} aria-hidden="true"><Lines lines={room} /></div>
        </div>
      </div>
      {sid && st !== "T8" && (
        <div className="mp-status-box" style={{ minHeight: sMin || undefined }}>
          <p className="mp-status mono" data-testid="session-status">{statusLine(status)}</p>
          <div className="mp-status-twin" ref={stwin} aria-hidden="true">{said.map((t) => <p key={t} className="mp-status mono">{t}</p>)}</div>
        </div>
      )}
      {form && (
        <div className="mp-truth-form" data-testid="session-truth-form">
          <NewSession compact />
          <button type="button" className="mp-link" onClick={() => setForm(false)} data-testid="session-truth-form-close">Close</button>
        </div>
      )}
    </div>
  );
}
