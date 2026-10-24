// What Auto learned about a model, in the picker table (3.1.9.0 R3, "Auto
// learns": outcomes/learn.py over outcomes.jsonl's checked agent tasks).
// One chip per task kind -- "code 4/5" -- muted while it has fewer checked
// tasks than the rule weighs (`counted`), struck through when the model is
// dropped for that kind (its rate under `models.learn.drop_below`); the
// hover says the numbers, the pick's weight and the window. The picker's
// "learned for" select narrows the chips to one kind and strikes the rows
// dropped for it.
import type { Learned, ModelRow } from "./types";

/** The task kinds any row has learned numbers for, in a stable order. */
export function learnedKinds(models: ModelRow[]): string[] {
  const seen = new Set<string>();
  for (const m of models) for (const k of Object.keys(m.learned || {})) seen.add(k);
  return [...seen].sort();
}

export function droppedFor(m: ModelRow, kind: string): boolean {
  return !!(kind && m.learned?.[kind]?.dropped);
}

function title(kind: string, l: Learned): string {
  const window = l.days ? `the last ${l.days} days` : "every row";
  const what = `${kind}: ${l.passed}/${l.n} checked tasks passed first time (${window}), ${l.picked} of them its own pick`;
  if (l.dropped) return `${what}; dropped for ${kind}: the auto pick weighs it ${l.weight.toFixed(3)} and the roster names it as dropped`;
  if (!l.counted) return `${what}; too few to weigh yet`;
  return `${what}; the auto pick weighs it ${l.weight.toFixed(3)}`;
}

export function LearnedChips({ m, kind }: { m: ModelRow; kind: string }) {
  const all = Object.entries(m.learned || {}).filter(([k]) => !kind || k === kind).sort(([a], [b]) => a.localeCompare(b));
  if (!all.length) return null;
  return (
    <span className="rm-learned" aria-label="learned">
      {all.map(([k, l]) => (
        <span key={k} className="og-chip mono rm-learned-chip" data-testid="model-learned" data-kind={k} data-dropped={l.dropped || undefined}
              data-counted={l.counted || undefined} title={title(k, l)}>
          {k} {l.passed}/{l.n}
        </span>
      ))}
    </span>
  );
}
