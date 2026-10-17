// The bio form (3.0.7.0 R2; bio-form.js in the classic page): the bio open in
// the Bios panel as fields -- its name, kind and description; its model
// preference (the model picker table and "Test this model"), fallback,
// effort and thinking; the tools it may or may not call (from the real
// registry, `GET tools`); its limits and its output. Save writes it to your
// scope (a shipped bio becomes your copy); a 422 lists the validator's lines.
import { useMemo } from "react";
import { Button } from "../../lib/ui";
import { editBio, saveBio, setKey, sub } from "./bioActions";
import { ListIn, NumberIn, Pick, TextIn } from "./controls";
import { ModelPicker } from "./ModelPicker";
import { openDialog, scopeLabel, shipped, useRoles } from "./store";
import type { Raw } from "./types";

const KINDS = ["main", "subagent", "researcher", "judge", "reviewer", "custom", "media"];

function Tools({ label, list, onChange, known, testid }: { label: string; list: string[]; onChange: (v: string[]) => void; known: string[]; testid: string }) {
  const rest = known.filter((t) => !list.includes(t));
  return (
    <div className="field re-field">
      <span className="field-label mono">{label}</span>
      <div className="rb-tools" data-testid={testid}>
        {list.map((t) => (
          <span key={t} className="og-chip mono rb-tool">
            {t}
            <button className="rb-x" aria-label={`Remove ${t}`} onClick={() => onChange(list.filter((x) => x !== t))}>×</button>
          </span>
        ))}
        <select className="input rb-add" value="" onChange={(e) => e.target.value && onChange([...list, e.target.value])} aria-label={`Add to ${label}`}>
          <option value="">+ add a tool</option>
          {rest.map((t) => <option key={t} value={t}>{t}</option>)}
        </select>
      </div>
    </div>
  );
}

export function BioForm() {
  const name = useRoles((s) => s.bio);
  const data = useRoles((s) => s.bioData);
  const d = useRoles((s) => s.bioDraft);
  const problems = useRoles((s) => s.bioProblems);
  const tools = useRoles((s) => s.tools);
  const busy = useRoles((s) => s.busy === "bio");
  const catalog = useRoles((s) => s.models);
  const refs = useMemo(() => catalog.map((m) => m.ref), [catalog]);
  if (!name) return <p className="muted">Pick a bio above, or drag one onto the canvas to add it to the lineup.</p>;
  if (!d || !data) return problems.length ? <p className="og-problems">{problems[0]}</p> : <div className="og-wait mono muted">reading {name}...</div>;
  const models = (d.models || {}) as Raw;
  const tl = (d.tools || {}) as Raw;
  const limits = (d.limits || {}) as Raw;
  const out = (d.output || {}) as Raw;
  const at = (section: string, key: string) => (v: unknown) => editBio((r) => setKey(sub(r, section), key, v));
  const top = (key: string) => (v: unknown) => editBio((r) => setKey(r, key, v));
  const arr = (v: unknown) => (Array.isArray(v) ? (v as string[]) : []);
  return (
    <div className="rb-form" data-testid="bio-form" data-bio={name}>
      <header className="re-assign-head">
        <b>{name}</b>
        <span className="rc-scope mono" data-scope={data.scope}>{shipped(data.scope) ? "shipped: saving makes your copy" : scopeLabel(data.scope)}</span>
      </header>
      <TextIn label="Description" value={String(d.description ?? "")} onCommit={top("description")} />
      <Pick label="Kind" value={String(d.kind ?? "subagent")} options={KINDS} onChange={top("kind")} />
      <TextIn label="Extends" placeholder="inherit every section from another bio" value={String(d.extends ?? "")} onCommit={top("extends")} />
      <div className="rail-label mono rb-sec">MODELS</div>
      <div className="field re-field">
        <span className="field-label mono">Preferred model</span>
        <ModelPicker value={String(models.preference ?? "")} onPick={at("models", "preference")} />
      </div>
      <Pick label="Fallback" value={String(models.fallback ?? "")} options={["", ...refs]} onChange={at("models", "fallback")} />
      <Pick label="Effort" value={String(models.effort ?? "")} options={["", "low", "medium", "high", "max"]} onChange={at("models", "effort")} />
      <Pick label="Thinking" value={String(models.thinking ?? "")} options={["", "native", "off"]} onChange={at("models", "thinking")} />
      <div className="rail-label mono rb-sec">TOOLS</div>
      <Tools label="Allow" list={arr(tl.allow)} onChange={at("tools", "allow")} known={tools} testid="bio-tools-allow" />
      <Tools label="Deny" list={arr(tl.deny)} onChange={at("tools", "deny")} known={tools} testid="bio-tools-deny" />
      <Pick label="Permission mode" value={String(tl.permission_mode ?? "")} options={["", "auto", "manual", "plan"]} onChange={at("tools", "permission_mode")} />
      <ListIn label="MCP servers" value={arr(tl.mcp_servers)} onCommit={at("tools", "mcp_servers")} />
      <div className="rail-label mono rb-sec">LIMITS</div>
      <NumberIn label="Max iterations" value={limits.max_iterations as number | undefined} onCommit={at("limits", "max_iterations")} />
      <TextIn label="Timeout" placeholder="20m, 2h, 90s" value={String(limits.timeout ?? "")} onCommit={at("limits", "timeout")} />
      <NumberIn label="Max budget (USD)" value={limits.max_budget_usd as number | undefined} onCommit={at("limits", "max_budget_usd")} />
      <NumberIn label="Concurrency" value={limits.concurrency as number | undefined} onCommit={at("limits", "concurrency")} />
      <div className="rail-label mono rb-sec">OUTPUT</div>
      <Pick label="Hand-back" value={String(out.handoff ?? "")} options={["", "summary", "full", "structured"]} onChange={at("output", "handoff")} />
      <TextIn label="Report to" placeholder="boss" value={String(out.report_to ?? "")} onCommit={at("output", "report_to")} />
      {problems.length > 0 && (
        <div className="re-save-problems" data-testid="bio-problems" role="alert">
          <b>Not saved: the validator says</b>
          <ul>{problems.map((p) => <li key={p}>{p}</li>)}</ul>
        </div>
      )}
      <div className="re-actions rb-actions">
        <Button variant="primary" size="sm" disabled={busy} onClick={() => void saveBio()} data-testid="bio-save">Save bio</Button>
        <Button size="sm" variant="ghost" disabled={shipped(data.scope)} onClick={() => openDialog({ kind: "delete-bio", name })} title={shipped(data.scope) ? "A shipped bio cannot be deleted" : "Delete this bio (asks first)"}>Delete</Button>
      </div>
    </div>
  );
}
