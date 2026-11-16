// The truth block over Session's Live drawing (3.6.0.2 R20 R21 R22 R23, section 4): which map the chosen session runs on
// and since when, S13 with [New session] when new sessions run on another map, T7 first while it runs a workflow that is
// a box on that map, T5 when its map changed; under it the status line. Every sentence is truth.ts's (TruthBlock builds
// none). R20: its height is reserved from the first draw for the longest state truth.ts gives for this session (a hidden
// twin of `reserve`, measured at the block's width, never clamped, never smaller once reserved), so the drawing below never
// moves when a fact changes. Never amber. [New session] opens the New session form in the drawer's corner (R5: the form
// starts a session, never this button).
import { useEffect, useLayoutEffect, useRef, useState } from "react";
import { api } from "../../lib/api";
import { useStore } from "../../lib/store";
import { useSessionRecord } from "../../lib/work/record";
import { lit, startLit } from "../crew/map/litStore";
import type { MapDetail } from "../crew/map/mapTypes";
import { nextMap, reserve, statusLine, truthLines, truthState, type Line, type TruthFacts } from "../crew/map/truth";
import { NewSession } from "./NewSession";
import { statusOf } from "./statusOf";

const LIVE = ["queued", "running", "paused", "waiting"];
const bodies = new Map<string, MapDetail | false>(); // {B}'s map, read once a page, only when a workflow runs (R22, R28)

/** {B}'s map body, once a workflow runs (after the first draw: never a fetch before it), else null. */
function useBody(name: string, want: boolean): MapDetail | null {
  const [, setN] = useState(0);
  useEffect(() => {
    if (!want || !name || bodies.has(name)) return;
    bodies.set(name, false);
    void api.get<MapDetail>(`crew/map/${name}`).then((d) => (bodies.set(name, d), setN((n) => n + 1)), () => undefined);
  }, [name, want]);
  return (want && bodies.get(name)) || null;
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

/** `f`: the session's facts (pick.ts factsOf), or `{ none: true, b }` for Empty; `sid`: the session ("" for Empty). */
export function TruthBlock({ f: given, sid }: { f: TruthFacts; sid: string }) {
  useEffect(() => startLit(), []);
  const rec = useSessionRecord(sid);
  const rows = (rec?.agents || []).map((a) => ({ ...a.row, agent_id: a.id }));
  const events = useStore(lit, (x) => (sid ? x.events[sid] : undefined)) || [];
  const flow = rows.find((r) => LIVE.includes(String(r.state || "")) && r.crew?.workflow)?.crew?.workflow || "";
  const B = nextMap(given.b);
  const body = useBody(B, !!flow && !given.none);
  const runs = !!flow && !!body && (body.map.boxes || []).some((b) => (b as { workflow?: string }).workflow === flow);
  const f: TruthFacts = { ...given, workflow: runs ? flow : null }; // R22: T7 only once B's body says W is a box on it
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
  useLayoutEffect(() => { // R20: the reserve, measured; it only grows (a fact never pulls the drawing up or down)
    const h = twin.current?.offsetHeight || 0;
    if (h > most.current + 0.5) (most.current = h, setMinH(h));
  });
  const [form, setForm] = useState(false);
  const st = truthState(f);
  const busy = !!given.busy;
  return (
    <div className="mp-truth" ref={root} data-testid="session-truth" data-state={st}>
      <div className="mp-truth-lines" style={{ minHeight: minH || undefined }}>
        <div className="cw-line mp-truth-said" data-testid="session-lit-line" data-state={st} data-sid={sid}>
          <Lines lines={lines} onNew={() => setForm(true)} />
        </div>
        <div className="cw-line mp-truth-said mp-truth-twin" ref={twin} aria-hidden="true"><Lines lines={room} /></div>
      </div>
      {sid && st !== "T8" && <p className="mp-status mono" data-testid="session-status">{statusLine(statusOf(rows, events, busy))}</p>}
      {form && (
        <div className="mp-truth-form" data-testid="session-truth-form">
          <NewSession compact />
          <button type="button" className="mp-link" onClick={() => setForm(false)} data-testid="session-truth-form-close">Close</button>
        </div>
      )}
    </div>
  );
}
