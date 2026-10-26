// Measure the found models (3.3.0.0 R5), under the Ollama card's found
// servers once Add wrote some: the models of the hosts just added, each with a
// tick, and **Measure the found models** -- one calibration per ticked model
// (`POST setup/ollama/measure`, the calibration `halo ollama calibrate` runs:
// the model is loaded at a few windows and the largest that sits fully in GPU
// memory is recorded in ~/.halo/ollama-fit.json), as a background job with a
// live log: one line per model ("qwen3:30b on pc: 32k fits, 65k does not (2
// min 10 s)") and the summary. `halo ollama discover --add --calibrate` does
// the same from a terminal.
import { Button } from "../../lib/ui";
import { measureTicked, pickModel, running, stopJob, useDiscover } from "./discover";

function Log() {
  const m = useDiscover((s) => s.measure);
  if (!m || !m.job) return null;
  const on = running(m);
  const lines = m.lines || [];
  const pending = on && m.line && !lines.includes(m.line) ? m.line : "";
  return (
    <div className="su-lines mono" data-ok={m.state === "done" || undefined} data-testid="setup-measure-log" data-state={m.state}>
      {lines.map((l, i) => (
        <div key={i} data-testid="setup-measure-line">{l}</div>
      ))}
      {pending && (
        <div className="muted" data-testid="setup-measure-pending">
          {pending}{m.total ? ` (${m.index} of ${m.total}, ${Math.round(m.elapsed || 0)} s)` : ""}
        </div>
      )}
      {!on && m.summary && <div data-testid="setup-measure-summary">{m.summary}</div>}
      {!on && !m.summary && m.line && <div data-testid="setup-measure-summary">{m.line}</div>}
    </div>
  );
}

export function OllamaMeasure() {
  const added = useDiscover((s) => s.added);
  const rows = useDiscover((s) => s.rows);
  const picks = useDiscover((s) => s.picks);
  const busy = useDiscover((s) => s.busy);
  const measuring = useDiscover((s) => running(s.measure));
  const shown = useDiscover((s) => !!s.measure?.job);
  if (!added.length && !shown) return null;
  const hosts = added.map((name) => ({ name, models: rows.find((r) => r.configured && r.name === name)?.models || [] }));
  const count = Object.values(picks).filter(Boolean).length;
  return (
    <div className="su-form" data-testid="setup-measure">
      <div className="su-sub">Measure the found models</div>
      <span className="su-note muted">
        Each ticked model is loaded at a few windows; the largest that sits fully in GPU memory is recorded, so the first real turn
        already knows its window (about a minute per model).
      </span>
      {hosts.map((h) => (
        <div key={h.name} className="su-card-row" data-testid="setup-measure-host" data-name={h.name}>
          <span className="mono">{h.name}</span>
          {h.models.length ? (
            h.models.map((m) => {
              const ref = `${m}@${h.name}`;
              return (
                <label key={ref} className="mono muted" data-testid="setup-measure-model" data-ref={ref}>
                  <input type="checkbox" checked={!!picks[ref]} disabled={measuring} onChange={(e) => pickModel(ref, e.target.checked)} /> {m}
                </label>
              );
            })
          ) : (
            <span className="muted">no models pulled yet</span>
          )}
        </div>
      ))}
      <div className="su-card-row">
        <Button size="sm" variant="primary" disabled={!count || measuring || !!busy} onClick={() => void measureTicked()} data-testid="setup-ollama-measure"
                title="Run the calibration for every ticked model, one at a time (halo ollama discover --calibrate)">
          {measuring ? "Measuring..." : `Measure the found models${count ? ` (${count})` : ""}`}
        </Button>
        {measuring && (
          <Button size="sm" variant="ghost" onClick={() => void stopJob("measure")} data-testid="setup-ollama-measure-stop"
                  title="Stop after the model being measured now">
            Stop
          </Button>
        )}
      </div>
      <Log />
    </div>
  );
}
