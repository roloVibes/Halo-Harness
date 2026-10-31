// A change's scope, a three-way pick (3.3.6.0 R5; ollama_steward/changes.py): keep (preselected for a change of
// yours), until this halo exits (until-restart), until the session ends (session). The tuning report's Apply, the
// KV dial's Apply and the changes list (re-scope a change) use it.
import type { Scope } from "../local/benchstore";

export const SCOPES: [Scope, string, string][] = [
  ["keep", "keep", "kept until you revert it"],
  ["until-restart", "until halo exits", "put back when this halo process exits"],
  ["session", "until the session ends", "put back when the session that made it ends"],
];

export function ScopePick({ value, onChange, name, testid = "scope-pick", disabled }: {
  value: Scope; onChange: (s: Scope) => void; name: string; testid?: string; disabled?: boolean;
}) {
  return (
    <span className="scope-pick mono" role="radiogroup" aria-label="how long the change holds" data-testid={testid} data-value={value}>
      {SCOPES.map(([id, label, title]) => (
        <label key={id} className="scope-opt" data-scope={id} title={title}>
          <input type="radio" name={name} value={id} checked={value === id} disabled={disabled} onChange={() => onChange(id)}
                 data-testid={`${testid}-opt`} data-scope={id} />
          {label}
        </label>
      ))}
    </span>
  );
}
