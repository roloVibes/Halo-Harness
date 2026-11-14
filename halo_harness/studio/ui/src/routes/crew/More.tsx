// More (rarely needed), the fold (3.6.0.0 R1; the design's "More holds only what the new agent format keeps"):
// fallback model, effort, thinking, limits (turns, minutes, money), files it always reads, its own worktree, offline,
// the acceptance check. Each a row with its plain line; the fallback is the shared model picker.
import { TextBox } from "../../lib/ui";
import { ModelSelect } from "../shared/ModelSelect";
import { setMore } from "./store";
import type { Agent } from "./types";
import { Switch } from "./Uses";

const EFFORTS = ["", "low", "medium", "high", "xhigh", "max"];

function Num({ label, line, value, onSet, testid, step = 1 }: { label: string; line: string; value?: number; onSet: (v?: number) => void; testid: string; step?: number }) {
  return (
    <label className="cw-more-row">
      <span className="cw-label mono">{label}</span>
      <input className="input mono cw-num" type="number" min={0} step={step} value={value ?? ""} data-testid={testid}
             onChange={(e) => onSet(e.target.value === "" ? undefined : Number(e.target.value))} />
      <span className="cw-line">{line}</span>
    </label>
  );
}

export function More({ a }: { a: Agent }) {
  const m = a.more || {};
  return (
    <details className="cw-more" data-testid="crew-more">
      <summary>More (rarely needed)</summary>
      <div className="cw-more-body">
        <ModelSelect label="FALLBACK MODEL" value={m.fallback || ""} onPick={(ref) => setMore({ fallback: ref || undefined })} testid="crew-fallback"
                     inherit={{ label: "none", model: "", text: "none: it stops when its model fails" }} hint="The model it moves to when its own fails." noTest />
        <label className="cw-more-row">
          <span className="cw-label mono">EFFORT</span>
          <select className="input mono" value={m.effort || ""} onChange={(e) => setMore({ effort: e.target.value || undefined })} data-testid="crew-effort">
            {EFFORTS.map((e) => <option key={e} value={e}>{e || "the model's own"}</option>)}
          </select>
          <span className="cw-line">How hard its model thinks per step.</span>
        </label>
        <div className="cw-sw">
          <Switch on={!!m.thinking} label="Thinking" onFlip={() => setMore({ thinking: !m.thinking || undefined })} testid="crew-thinking" />
          <div className="cw-sw-text"><b>Thinking</b><span className="cw-line">Shows its reasoning where the model has it.</span></div>
        </div>
        <Num label="TURNS" line="At most this many steps a task (empty: no limit)." value={m.max_turns} onSet={(v) => setMore({ max_turns: v })} testid="crew-max-turns" />
        <Num label="MINUTES" line="At most this long a task." value={m.max_minutes} onSet={(v) => setMore({ max_minutes: v })} testid="crew-max-minutes" />
        <Num label="DOLLARS" line="At most this much a task; it stops there." value={m.max_usd} step={0.5} onSet={(v) => setMore({ max_usd: v })} testid="crew-max-usd" />
        <label className="cw-more-row cw-more-wide">
          <span className="cw-label mono">FILES IT ALWAYS READS</span>
          <TextBox mono maxRows={6} value={(m.reads || []).join("\n")} placeholder="one file a line, e.g. SECURITY.md" data-testid="crew-reads"
                   onChange={(e) => setMore({ reads: e.target.value.split("\n").map((x) => x.trim()).filter(Boolean) })} />
        </label>
        <div className="cw-sw">
          <Switch on={!!m.worktree} label="Its own worktree" onFlip={() => setMore({ worktree: !m.worktree || undefined })} testid="crew-worktree" />
          <div className="cw-sw-text"><b>Its own worktree</b><span className="cw-line">Works in a copy of the repo, so your tree stays as it is.</span></div>
        </div>
        <div className="cw-sw">
          <Switch on={!!m.offline} label="Offline" onFlip={() => setMore({ offline: !m.offline || undefined })} testid="crew-offline" />
          <div className="cw-sw-text"><b>Offline</b><span className="cw-line">Never uses the web, even when it may.</span></div>
        </div>
        <label className="cw-more-row cw-more-wide">
          <span className="cw-label mono">ITS CHECK</span>
          <input className="input" value={m.check?.ask || ""} placeholder="a request it must answer, e.g. Reply ok" data-testid="crew-check-ask"
                 onChange={(e) => setMore({ check: e.target.value ? { ask: e.target.value, expect: m.check?.expect } : undefined })} />
          <input className="input mono" value={m.check?.expect || ""} placeholder="a word the reply holds" data-testid="crew-check-expect"
                 onChange={(e) => setMore({ check: m.check?.ask ? { ask: m.check.ask, expect: e.target.value || undefined } : undefined })} />
        </label>
      </div>
    </details>
  );
}
