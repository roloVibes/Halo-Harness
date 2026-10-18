// The bio form's sections (3.1.1.0 R3: every field the terminal's bio view
// shows is here): models (preference with the picker and "Test this model",
// fallback, effort, thinking, the context budget), tools (allow and deny from
// the real registry, MCP servers, the permission mode, the rules), context
// (files, skills, the memory namespace, prompt notes), limits, output,
// environment and acceptance. Each field's help line is field_help.py's
// (GET /api/field-help), the same line the TUI shows.
import { useMemo, type ReactNode } from "react";
import { useHelpGroup } from "../../lib/fieldHelp";
import { editBio, setKey, sub } from "./bioActions";
import { Check, ListIn, NumberIn, Pick, Row, TextIn } from "./controls";
import { ModelPicker } from "./ModelPicker";
import { useRoles } from "./store";
import type { Raw } from "./types";

export const EFFORTS = ["", "low", "medium", "high", "xhigh", "max"];

export const at = (section: string, key: string) => (v: unknown) => editBio((r) => setKey(sub(r, section), key, v));
export const arr = (v: unknown) => (Array.isArray(v) ? (v as string[]) : []);
const of = (d: Raw, section: string) => (d[section] && typeof d[section] === "object" && !Array.isArray(d[section]) ? d[section] : {}) as Raw;

export function Sec({ title, children }: { title: string; children: ReactNode }) {
  return (
    <>
      <div className="rail-label mono rb-sec">{title}</div>
      {children}
    </>
  );
}

function Tools({ label, list, onChange, known, testid, changed, hint }: { label: string; list: string[]; onChange: (v: string[]) => void; known: string[]; testid: string; changed?: boolean; hint?: string }) {
  const rest = known.filter((t) => !list.includes(t));
  return (
    <div className={"field re-field" + (changed ? " cc-changed" : "")} data-coach-changed={changed || undefined}>
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
      {hint && <div className="field-hint">{hint}</div>}
    </div>
  );
}

function CheckRow({ label, value, onChange, hint, testid }: { label: string; value: boolean; onChange: (v: boolean) => void; hint?: string; testid?: string }) {
  return (
    <Row hint={hint}>
      <Check label={label} value={value} onChange={onChange} testid={testid} />
    </Row>
  );
}

export function BioFields({ d, mark }: { d: Raw; mark: (field: string) => boolean }) {
  const h = useHelpGroup("bio");
  const tools = useRoles((s) => s.tools);
  const catalog = useRoles((s) => s.models);
  const refs = useMemo(() => catalog.map((m) => m.ref), [catalog]);
  const models = of(d, "models"), tl = of(d, "tools"), ctx = of(d, "context"), limits = of(d, "limits");
  const out = of(d, "output"), env = of(d, "environment"), acc = of(d, "acceptance");
  const memory = (ctx.memory && typeof ctx.memory === "object" ? ctx.memory : {}) as Raw;
  const changed = (f: string) => (mark(f) ? "cc-changed" : undefined);
  return (
    <>
      <Sec title="MODELS">
        <div className={"field re-field" + (mark("models.preference") ? " cc-changed" : "")} data-coach-changed={mark("models.preference") || undefined}>
          <span className="field-label mono">Preferred model</span>
          <ModelPicker value={String(models.preference ?? "")} onPick={at("models", "preference")} />
          {h["models.preference"] && <div className="field-hint">{h["models.preference"]}</div>}
        </div>
        <Pick label="Fallback" hint={h["models.fallback"]} value={String(models.fallback ?? "")} options={["", ...refs]} onChange={at("models", "fallback")} testid="bio-fallback" />
        <Pick label="Effort" hint={h["models.effort"]} value={String(models.effort ?? "")} options={EFFORTS} onChange={at("models", "effort")} testid="bio-effort" />
        <Pick label="Thinking" hint={h["models.thinking"]} value={String(models.thinking ?? "")} options={["", "native", "off"]} onChange={at("models", "thinking")} />
        <NumberIn label="Context budget (0-1)" hint={h["models.context_budget"]} value={models.context_budget as number | undefined} onCommit={at("models", "context_budget")} testid="bio-context-budget" />
      </Sec>
      <Sec title="TOOLS">
        <Tools label="Allow" hint={h["tools.allow"]} list={arr(tl.allow)} onChange={at("tools", "allow")} known={tools} testid="bio-tools-allow" changed={mark("tools.allow")} />
        <Tools label="Deny" hint={h["tools.deny"]} list={arr(tl.deny)} onChange={at("tools", "deny")} known={tools} testid="bio-tools-deny" changed={mark("tools.deny")} />
        <ListIn label="MCP servers" hint={h["tools.mcp_servers"]} value={arr(tl.mcp_servers)} onCommit={at("tools", "mcp_servers")} />
        <Pick label="Permission mode" hint={h["tools.permission_mode"]} value={String(tl.permission_mode ?? "")} options={["", "auto", "manual", "plan"]} onChange={at("tools", "permission_mode")} />
        <TextIn label="Rules (one per line)" area hint={h["tools.rules"]} placeholder="deny Bash(git push*)" value={arr(tl.rules).join("\n")}
                onCommit={(v) => at("tools", "rules")(v.split("\n").map((x) => x.trim()).filter(Boolean))} testid="bio-rules" />
      </Sec>
      <Sec title="CONTEXT">
        <ListIn label="Files" hint={h["context.files"]} placeholder="CLAUDE.md, plans/STATUS.md" value={arr(ctx.files)} onCommit={at("context", "files")} testid="bio-context-files" />
        <ListIn label="Skills" hint={h["context.skills"]} value={arr(ctx.skills)} onCommit={at("context", "skills")} />
        <TextIn label="Memory namespace" hint={h["context.memory"]} value={String(memory.namespace ?? "")} testid="bio-memory"
                onCommit={(v) => at("context", "memory")(v.trim() ? { ...memory, enabled: true, namespace: v.trim() } : undefined)} />
        <div className={changed("context.prompt_notes")} data-coach-changed={mark("context.prompt_notes") || undefined}>
          <TextIn label="Prompt notes" area hint={h["context.prompt_notes"]} placeholder="lines added after the bio's prompt" value={String(ctx.prompt_notes ?? "")} onCommit={at("context", "prompt_notes")} testid="bio-prompt-notes" />
        </div>
      </Sec>
      <Sec title="LIMITS">
        <NumberIn label="Max iterations" hint={h["limits.max_iterations"]} value={limits.max_iterations as number | undefined} onCommit={at("limits", "max_iterations")} testid="bio-max-iterations" />
        <TextIn label="Timeout" hint={h["limits.timeout"]} placeholder="20m, 2h, 90s" value={String(limits.timeout ?? "")} onCommit={at("limits", "timeout")} />
        <NumberIn label="Max budget (USD)" hint={h["limits.max_budget_usd"]} value={limits.max_budget_usd as number | undefined} onCommit={at("limits", "max_budget_usd")} testid="bio-max-budget" />
        <NumberIn label="Concurrency" hint={h["limits.concurrency"]} value={limits.concurrency as number | undefined} onCommit={at("limits", "concurrency")} />
      </Sec>
      <Sec title="OUTPUT">
        <Pick label="Hand-back" hint={h["output.handoff"]} value={String(out.handoff ?? "")} options={["", "summary", "full", "structured"]} onChange={at("output", "handoff")} />
        <TextIn label="Report to" hint={h["output.report_to"]} placeholder="boss" value={String(out.report_to ?? "")} onCommit={at("output", "report_to")} />
      </Sec>
      <Sec title="ENVIRONMENT">
        <CheckRow label="Own git worktree" hint={h["environment.worktree"]} value={!!env.worktree} onChange={(v) => at("environment", "worktree")(v || undefined)} testid="bio-worktree" />
        <CheckRow label="Offline" hint={h["environment.offline"]} value={!!env.offline} onChange={(v) => at("environment", "offline")(v || undefined)} testid="bio-offline" />
      </Sec>
      <Sec title="ACCEPTANCE">
        <TextIn label="Prompt" hint={h["acceptance.prompt"]} value={String(acc.prompt ?? "")} onCommit={at("acceptance", "prompt")} testid="bio-accept-prompt" />
        <TextIn label="Expect" hint={h["acceptance.expect"]} value={String(acc.expect ?? "")} onCommit={at("acceptance", "expect")} />
      </Sec>
    </>
  );
}
