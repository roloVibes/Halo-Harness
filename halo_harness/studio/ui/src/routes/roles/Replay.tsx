// The replay bar along the bottom of the Roles canvas (3.0.7.0 R2; D12):
// play / pause, the speed, the scrub, the clock, the session's cost so far
// and who works at that moment. The cards light up from the replay's agents
// (live.ts agentsAt) while it is open; x or Esc closes it and the canvas goes
// back to what runs now. data-t (seconds since the start) and data-lit (who
// works) say where the replay stands.
import { useEffect } from "react";
import { closeReplay, costAt, play, scrub, setSpeed, SPEEDS } from "../fleet/replay";
import { agentsAt } from "./live";
import { useRoles } from "./store";

const mmss = (v: number) => {
  const s = Math.max(0, Math.round(v));
  const h = Math.floor(s / 3600), m = Math.floor((s % 3600) / 60), x = s % 60;
  return (h ? h + ":" + String(m).padStart(2, "0") : String(m)) + ":" + String(x).padStart(2, "0");
};

export function ReplayBar() {
  const r = useRoles((s) => s.replay);
  const open = r !== null;
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key !== "Escape" || (e.target as HTMLElement | null)?.closest?.("input, textarea, select")) return;
      e.preventDefault();
      e.stopImmediatePropagation();
      closeReplay();
    };
    window.addEventListener("keydown", onKey, true);
    return () => window.removeEventListener("keydown", onKey, true);
  }, [open]);
  if (!r) return null;
  const span = Math.max(1, r.t1 - r.t0);
  const lit = agentsAt(r, r.t).filter((a) => a.state === "running" || a.state === "waiting");
  return (
    <div className="rc-replay" role="group" aria-label="Replay" data-testid="replay-bar" data-t={Math.round(r.t - r.t0)} data-lit={lit.map((a) => a.name).join(",")}
         data-playing={r.playing || undefined}>
      <button className="btn btn-primary btn-sm rc-replay-play" onClick={() => play(!r.playing)} title="Play / pause" data-testid="replay-play">
        {r.playing ? "❚❚" : "▶"}
      </button>
      <select className="input rc-replay-speed" value={r.speed} onChange={(e) => setSpeed(Number(e.target.value))} title="Speed" aria-label="Speed">
        {SPEEDS.map((s) => <option key={s} value={s}>{s}×</option>)}
      </select>
      <div className="rc-replay-mid">
        <div className="rc-replay-line">
          <b>Replay</b> <span className="replay-title">{r.meta.title || r.meta.session_id}</span>
          <span className="mono muted">{r.meta.harness}</span>
          <span className="spacer" />
          <span className="mono">{mmss(r.t - r.t0)} / {mmss(span)}</span>
          <span className="mono rc-replay-cost">${costAt(r, r.t).toFixed(4)}</span>
        </div>
        <input type="range" min={0} max={1000} value={Math.round(((r.t - r.t0) / span) * 1000)} onChange={(e) => scrub(Number(e.target.value) / 1000)}
               aria-label="Scrub" data-testid="replay-scrub" />
        <div className="rc-replay-lit muted">{lit.length ? lit.map((a) => `${a.name} ${a.state === "waiting" ? "waits" : "works"}`).join(" · ") : "nobody works right now"}</div>
      </div>
      <button className="icon-btn rc-replay-close" onClick={closeReplay} title="Back to what runs now (Esc)" aria-label="Close the replay" data-testid="replay-close">×</button>
    </div>
  );
}
