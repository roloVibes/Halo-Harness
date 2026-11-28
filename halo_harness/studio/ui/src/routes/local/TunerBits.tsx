// 3.6.0.25 T batch 2: "Tune with <model>" under "Find the best window" (ollama_steward/tuner.py). With no tuner model
// set (Settings -> Ollama -> Tuner model) it is one closed line that says what a tuner would do (and the texts a tuner
// wrote before, still removable). Set, the offer says
// which model is called, what is sent, the cost and what it writes, before a start; then its rounds with Stop and its
// cost when done; then the texts it wrote, each "written by <model>" and removable -- never shown as a measurement.
import { Button } from "../../lib/ui";
import type { Note, SweepAnswer } from "./sweepRows";

const TITLES: Record<string, string> = { diagnosis: "DIAGNOSIS", advice: "SERVER ADVICE (never run by Halo)", guide: "GUIDE" };

function NoteBox({ n, onRemove }: { n: Note; onRemove: () => void }) {
  return (
    <div className="lc-tuner-note" data-testid="local-tuner-note" data-kind={n.kind}>
      <div className="rail-label mono">{TITLES[n.kind] || n.kind} · {n.by_line}</div>
      {n.text && <p className="lc-why">{n.text}</p>}
      {n.best_at?.length ? <p className="lc-why">good at: {n.best_at.join("; ")}</p> : null}
      {n.avoid?.length ? <p className="lc-why">avoid: {n.avoid.join("; ")}</p> : null}
      {(n.settings || []).map((s) => (
        <div key={s.key} className="lc-tuner-setting" data-testid="local-tuner-setting" data-key={s.key}>
          <p className="lc-why"><span className="mono">{s.key}={s.value}</span>: {s.why}</p>
          {Object.entries(s.server || {}).map(([os, l]) => (
            <p key={os} className="mono muted lc-why">{os}: {l.set} (revert: {l.revert}; then {l.restart})</p>
          ))}
        </div>
      ))}
      {n.dropped ? <p className="muted lc-why">{n.dropped} setting{n.dropped === 1 ? "" : "s"} not on the list dropped</p> : null}
      <Button size="sm" variant="ghost" onClick={onRemove} data-testid="local-tuner-remove" title="removes this text from Halo's notes">Remove</Button>
    </div>
  );
}

export function TunerBits({ a, start, stop, remove }: {
  a: SweepAnswer; start: () => void; stop: () => void; remove: (kind: string) => void;
}) {
  const t = a.tuner;
  const notes = Object.values(a.notes || {});
  if (!t) return null;
  const kept = notes.map((n) => <NoteBox key={n.kind} n={n} onRemove={() => remove(n.kind)} />);
  if (!t.tuner) {  // the closed line stands for the job only: what a tuner wrote before stays here, removable
    return (
      <>
        <details className="lc-tuner" data-testid="local-tuner-off">
          <summary className="muted lc-why">{t.line}</summary>
        </details>
        {kept.length ? <div className="lc-tuner" data-testid="local-tuner-notes">{kept}</div> : null}
      </>
    );
  }
  const job = a.tuner_job;
  const live = !!job && !job.done;
  return (
    <div className="lc-tuner" data-testid="local-tuner" data-running={live || undefined}>
      <div className="rail-label mono">TUNE WITH {t.tuner}</div>
      <p className="lc-why" data-testid="local-tuner-offer">calls {t.tuner}; sends {t.sends}; costs {t.cost}; writes {t.writes}</p>
      <div className="lc-sweep-go">
        {live ? (
          <Button size="sm" onClick={stop} data-testid="local-tuner-stop" title="stops before the next round">Stop</Button>
        ) : (
          <Button size="sm" variant="primary" onClick={start} data-testid="local-tuner-start">Tune with {t.tuner}</Button>
        )}
      </div>
      {job && (
        <ul className="lc-sweep-lines mono muted" data-testid="local-tuner-lines">
          {(live ? job.lines.slice(-6) : [job.line]).map((x, i) => <li key={i}>{x}</li>)}
        </ul>
      )}
      {kept}
    </div>
  );
}
