// FitMeter (3.3.5.0 R0b, the first of "Local"'s five ideas): will this model
// run here at this window? One small bar beside a model row: fits (green,
// every layer on the GPU with room), tight (amber: only with every layer
// forced on), spill (red: part on the CPU), no (red, empty: it does not fit
// this machine), cloud (accent: the provider runs it), unknown (faint: no
// hardware card read yet). `data-level` carries the level, the title says why
// (providers/fit_meter.py writes both). 3.3.6.0 R1: `word` adds the battery's measured speed ("fits, ~187 tok/s at 32k").
export type Fit = { level: string; at_window?: number | null; gpu_window?: number | null; why?: string; word?: string };

const LEVELS = ["fits", "tight", "spill", "no", "cloud", "unknown"];

export function FitMeter({ fit, label }: { fit?: Fit | null; label?: boolean }) {
  if (!fit || !fit.level) return null;
  const level = LEVELS.includes(fit.level) ? fit.level : "unknown";
  const title = `fit here: ${level}${fit.why ? ` -- ${fit.why}` : ""}`;
  return (
    <span className="fit-meter" data-testid="fit-meter" data-level={level} title={title} aria-label={title}>
      <span className="fit-meter-bar" aria-hidden="true"><span className="fit-meter-fill" /></span>
      {label !== false && <span className="fit-meter-word mono">{level === "unknown" ? "?" : fit.word || level}</span>}
    </span>
  );
}
