// The scrubber under Live's canvas (3.4.1.0 R1 "Time"), the ONE replay control: the session's time axis with its phase
// bands (thinking, a tool, writing, waiting on you, idle: the 3.3.16.2 words) and one mark per spawn, hand-off, ask,
// failure and finish (hover: what it was). Dragging redraws the canvas as it was at that moment (replay.ts); Play runs it
// forward at 1x / 4x / 16x; Now returns to what runs. Over the session drawn now it shows the axis up to now, read when
// the pointer comes to it (GET fleet/replay), and a drag rewinds that session. Save this run's replay and Export a clip
// say what they hold and write before they write (ReplaySave.tsx). data-t (seconds since the start), data-t10 (tenths:
// what the range holds), data-lit (who works), data-playing say where it stands.
import { useEffect, useState } from "react";
import { api } from "../../../lib/api";
import { createStore, useStore } from "../../../lib/store";
import { Button } from "../../../lib/ui";
import { cost as money } from "../../orchestra/format";
import { backToNow, liveReplay, openLiveReplay, play, scrubTo, setSpeed, SPEEDS, useLiveReplay } from "./replay";
import { ClipDialog, SaveDialog } from "./ReplaySave";
import { costAt, fromSession, litAt, mmss, type Mark, type SessionTimeline, type Timeline } from "./timeline";

const KIND: Record<string, string> = { spawn: "started", handoff: "handed back", ask: "asked you", fail: "failed", finish: "finished" };

/** The axis of the session drawn now (before any rewind), read when the pointer comes to the scrubber. */
const axis = createStore<{ sid: string; tl: Timeline | null; at: number }>({ sid: "", tl: null, at: 0 });
function readAxis(sid: string): void {
  const s = axis.get();
  if (!sid || (s.sid === sid && Date.now() - s.at < 5000)) return;
  axis.update(() => ({ sid, at: Date.now(), ...(s.sid === sid ? {} : { tl: null }) }));
  void api.get<SessionTimeline>("fleet/replay", { session: sid, harness: "local" })
    .then((m) => axis.get().sid === sid && axis.update(() => ({ tl: fromSession(m, sid) }))).catch(() => undefined);
}

/** What it had cost at the scrubber's moment; 3.4.1.1 (60): "unknown at this moment" where the record cannot say. */
function ReplayCost({ tl, t }: { tl: Timeline; t: number }) {
  const usd = costAt(tl, t);
  return <span className="scr-cost" data-testid="replay-cost" data-unknown={usd === null || undefined}
               title={usd === null ? "A goal run's record gives each lane's cost when it ends: before that, the cost is unknown" : "What it had cost at this moment"}>
    {usd === null ? "unknown at this moment" : money(usd)}</span>;
}

function Axis({ tl, t0, t1, at }: { tl: Timeline | null; t0: number; t1: number; at: number }) {
  const x = (t: number) => ((t - t0) / Math.max(1e-6, t1 - t0)) * 1000;
  const marks = (tl?.marks || []).filter((m) => m.t >= t0 && m.t <= t1);
  return (
    <svg className="scr-axis" viewBox="0 0 1000 28" preserveAspectRatio="none" aria-hidden="true">
      {(tl?.bands || []).map((b) => (
        <rect key={b.t0 + b.phase} className="scr-band" data-phase={b.phase} data-testid="replay-band" x={x(b.t0)} y={b.phase === "idle" ? 13 : 9}
              width={Math.max(0.6, x(Math.min(t1, b.t1)) - x(b.t0))} height={b.phase === "idle" ? 2 : 10} />
      ))}
      {marks.map((m: Mark, i) => (
        <rect key={i} className="scr-mark" data-kind={m.kind} data-testid="replay-mark" x={x(m.t) - 1} y={m.kind === "ask" || m.kind === "fail" ? 0 : 3}
              width={2} height={m.kind === "ask" || m.kind === "fail" ? 28 : 22}><title>{`${mmss(m.t - t0)} ${m.name} ${KIND[m.kind]}${m.text ? ": " + m.text : ""}`}</title></rect>
      ))}
      <rect className="scr-head" x={x(at) - 1.5} y={0} width={3} height={28} />
    </svg>
  );
}

type Props = { sid: string; title: string; started: number | null; lineup: string };

export function Scrubber({ sid, title, started, lineup }: Props) {
  const r = useLiveReplay();
  const ax = useStore(axis, (s) => (s.sid === sid ? s.tl : null));
  const [dialog, setDialog] = useState<"" | "save" | "clip">("");
  const [now, setNow] = useState(() => Date.now() / 1000);
  useEffect(() => { if (!r) { const id = window.setInterval(() => setNow(Date.now() / 1000), 1000); return () => window.clearInterval(id); } }, [r]);
  useEffect(() => void (!r && sid && readAxis(sid)), [r, sid]);
  useEffect(() => { // Esc on the page (not in a field, not taken by a dialog or a drawer): back to now
    if (!r) return;
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && !e.defaultPrevented && !(e.target as HTMLElement | null)?.closest?.("input:not([type=range]), textarea, select") && backToNow();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [!!r]); // eslint-disable-line react-hooks/exhaustive-deps
  const tl = r ? r.tl : ax;
  const t0 = tl ? tl.t0 : started ?? now - 60;
  const t1 = r ? r.tl.t1 : Math.max(now, tl?.t1 || 0, t0 + 1);
  const at = r ? r.t : t1;
  const span = Math.max(1, t1 - t0);
  const lit = r ? litAt(r.nodes) : [];
  const onScrub = (v: number) => {
    const t = t0 + v / 10;
    if (liveReplay.get().r) return scrubTo(t);
    if (!liveReplay.get().busy && sid) void openLiveReplay("session", sid, title, t, true);
  };
  const kind = r?.kind || "session";
  const track = ( // over the session running now: one slim row (the canvas keeps its height); a replay: its own row
    <div className="scr-track">
      <Axis tl={tl} t0={t0} t1={t1} at={at} />
      <input type="range" className="scr-range" min={0} max={Math.round(span * 10)} step={1} value={Math.round((at - t0) * 10)} onChange={(e) => onScrub(Number(e.target.value))}
             aria-label="Scrub: drag back in time" aria-valuetext={`${mmss(at - t0)} of ${mmss(span)}`} data-testid="replay-scrub" disabled={!r && !sid} />
    </div>
  );
  const saveWhy = kind === "file" ? "This is a saved replay file already" : kind === "mission" ? "A mission is the fleet pack's: it is kept and compared from its report, not saved as a replay file" : "";
  return (
    <div className="scr mono" role="group" aria-label="Time: scrub the session back, play it forward" data-testid="replay-bar" data-mode={r ? "replay" : "live"}
         data-t={Math.round(at - t0)} data-t10={Math.round((at - t0) * 10)} data-lit={lit.join(",")} data-playing={r?.playing || undefined}
         data-replay={r?.id || undefined} data-kind={r?.kind || undefined} data-marks={tl?.marks.length ?? 0} data-speed={r?.speed || undefined}
         onPointerEnter={() => !r && readAxis(sid)}>
      <div className="scr-row">
        <Button size="sm" variant={r?.playing ? "default" : "primary"} onClick={() => (r ? play(!r.playing) : void openLiveReplay("session", sid, title, t0, true).then((ok) => ok && play(true)))}
                title={r?.playing ? "Pause" : "Play it forward from here (from the start at the end)"} data-testid="replay-play" disabled={!r && !sid}>{r?.playing ? "Pause" : "Play"}</Button>
        {r ? <span className="segmented scr-speed" role="group" aria-label="Speed" data-testid="replay-speed">
          {SPEEDS.map((s) => <button key={s} className={r.speed === s ? "on" : ""} aria-pressed={r.speed === s} onClick={() => setSpeed(s)} data-speed={s}>{s}x</button>)}
        </span> : track}
        <span className="scr-clock" data-testid="replay-clock">{mmss(at - t0)} / {mmss(span)}</span>
        {r && <ReplayCost tl={r.tl} t={r.t} />}
        {r && <span className="scr-title replay-title" title={r.title}>{r.title}</span>}
        {r && <span className="spacer" />}
        {r && <Button size="sm" variant="ghost" onClick={() => setDialog("save")} disabled={!!saveWhy} title={saveWhy || "Save this run's replay as one file you can open anywhere (says what it holds first)"} data-testid="replay-save">Save this run's replay</Button>}
        {r && <Button size="sm" variant="ghost" onClick={() => setDialog("clip")} disabled={kind === "mission"} title={kind === "mission" ? "A clip is filmed from a saved replay: a mission's is the fleet pack's report" : "Film a range of it as one animated file (says what it writes first)"} data-testid="replay-clip">Export a clip</Button>}
        <Button size="sm" onClick={backToNow} disabled={!r} title="Now: back to what runs (Esc on the canvas)" data-testid="replay-close">Now</Button>
      </div>
      {r && track}
      {r && r.tl.coarse && <div className="scr-note muted" data-testid="replay-coarse">A mission's replay has each part's start and end only: who existed and how it ended, not each step.</div>}
      {r && !r.tl.coarse && r.tl.endsOnly && <div className="scr-note muted" data-testid="replay-coarse">A goal run's record holds each lane's state changes, not each step; a lane's cost is known when it ends.</div>}
      {dialog === "save" && r && <SaveDialog r={r} lineup={lineup} onClose={() => setDialog("")} />}
      {dialog === "clip" && r && <ClipDialog r={r} lineup={lineup} onClose={() => setDialog("")} />}
    </div>
  );
}
