// One step of the workflow form (3.6.0.0 R2; the approved mock's step row): its name; up / down; take it out; its agents
// as chips (several chips work at the same time; "+ agent" adds one of yours); Gets; Hands on; When it runs (always /
// only when the task needs ... / only when the task says ... / only when I ask); Repeat until, with "at most N times".
// A chip naming an agent that is not one of yours says so. A builder line that would change this step shows under it.
import { Button } from "../../../lib/ui";
import { useCrew } from "../store";
import type { Change, Step, When } from "../types";
import { costNow, moveStep, removeStep, setStep, useFlows } from "./flowStore";

const NONE: string[] = [];
const KINDS: [string, string][] = [["always", "always"], ["needs", "only when the task needs ..."], ["says", "only when the task says ..."], ["ask", "only when I ask for it"]];
const kindOf = (w?: When) => (!w || w === "always" ? "always" : w === "ask" ? "ask" : "needs" in w ? "needs" : "says");
const wordsOf = (w?: When) => (w && typeof w === "object" ? ("needs" in w ? w.needs : w.says).join(", ") : "");
const words = (t: string) => t.split(/[,\s]+/).map((x) => x.trim().toLowerCase()).filter(Boolean);

function whenFrom(kind: string, text: string): When {
  if (kind === "needs") return { needs: words(text).length ? words(text) : ["pdf"] };
  if (kind === "says") return { says: words(text).length ? words(text) : ["fix"] };
  return kind === "ask" ? "ask" : "always";
}

function Chips({ s, i }: { s: Step; i: number }) {
  const mine = useCrew((c) => c.agents);
  const starters = useCrew((c) => c.starters);
  const missing = useFlows((f) => costNow(f)?.missing || NONE);
  const left = [...mine, ...starters].filter((a) => !s.agents.includes(a.name));
  return (
    <div className="fl-chips" data-testid="flow-step-agents">
      {s.agents.map((a, k) => (
        <span key={a} className="fl-chip" data-missing={missing.includes(a) || undefined} data-testid="flow-chip" data-name={a}
              title={missing.includes(a) ? `${a} is not an agent of yours yet: make it in 1 · Agents, or ask the builder` : a}>
          <span className="fl-chip-name">{a}{missing.includes(a) ? " (not an agent yet)" : ""}</span>
          <button type="button" className="fl-x" aria-label={`Take ${a} out of step ${i + 1}`} title={`Take ${a} out`}
                  onClick={() => setStep(i, { agents: s.agents.filter((_x, j) => j !== k) })}>×</button>
        </span>
      ))}
      <select className="input fl-add-agent" value="" aria-label={`Add an agent to step ${i + 1}`} data-testid="flow-chip-add"
              onChange={(e) => e.target.value && setStep(i, { agents: [...s.agents, e.target.value] })}>
        <option value="">+ agent</option>
        {left.map((a) => <option key={`${a.scope}:${a.name}`} value={a.name}>{a.name}{a.scope === "starter" ? " (starter)" : ""}</option>)}
      </select>
      {s.agents.length > 1 && <span className="cw-line fl-same">these work at the same time</span>}
    </div>
  );
}

function Repeat({ s, i }: { s: Step; i: number }) {
  if (!s.repeat)
    return <Button onClick={() => setStep(i, { repeat: { until: "the tests pass", max: 3 } })} data-testid="flow-repeat-add">+ repeat this step until...</Button>;
  const r = s.repeat;
  return (
    <div className="fl-repeat">
      <input className="input" value={r.until} aria-label={`Step ${i + 1}: repeat until`} data-testid="flow-repeat-until"
             onChange={(e) => setStep(i, { repeat: { ...r, until: e.target.value } })} />
      <span className="cw-row">
        <span className="cw-line">at most</span>
        <input className="input fl-num" type="number" min={1} max={10} value={r.max} aria-label={`Step ${i + 1}: at most how many times`} data-testid="flow-repeat-max"
               onChange={(e) => setStep(i, { repeat: { ...r, max: Math.max(1, Math.min(10, Number(e.target.value) || 1)) } })} />
        <span className="cw-line">times (10 at most)</span>
        <Button onClick={() => setStep(i, { repeat: undefined })} data-testid="flow-repeat-off">no repeat</Button>
      </span>
    </div>
  );
}

export function StepRow({ s, i, n, notes }: { s: Step; i: number; n: number; notes: Change[] }) {
  const kind = kindOf(s.when);
  return (
    <div className="fl-step" data-testid="flow-step" data-n={i + 1} data-name={s.name}>
      <div className="fl-step-top">
        <span className="fl-n mono">STEP {i + 1}</span>
        <input className="input fl-step-name" value={s.name} aria-label={`Step ${i + 1} name`} data-testid="flow-step-name"
               onChange={(e) => setStep(i, { name: e.target.value })} />
        <span className="fl-ord">
          <Button onClick={() => moveStep(i, -1)} disabled={!i} aria-label={`Move step ${i + 1} up`} title="Move up" data-testid="flow-step-up">↑</Button>
          <Button onClick={() => moveStep(i, 1)} disabled={i >= n - 1} aria-label={`Move step ${i + 1} down`} title="Move down" data-testid="flow-step-down">↓</Button>
          <Button variant="danger" onClick={() => removeStep(i)} aria-label={`Take step ${i + 1} out`} title="Take the step out" data-testid="flow-step-remove">×</Button>
        </span>
      </div>
      <Chips s={s} i={i} />
      <div className="fl-grid">
        <label className="cw-field"><span className="cw-label mono">Gets</span>
          <input className="input" value={s.gets || ""} onChange={(e) => setStep(i, { gets: e.target.value })} placeholder="the task" data-testid="flow-step-gets" /></label>
        <label className="cw-field"><span className="cw-label mono">Hands on</span>
          <input className="input" value={s.hands || ""} onChange={(e) => setStep(i, { hands: e.target.value })} placeholder="its result" data-testid="flow-step-hands" /></label>
        <label className="cw-field"><span className="cw-label mono">When it runs</span>
          <select className="input" value={kind} data-testid="flow-step-when" onChange={(e) => setStep(i, { when: whenFrom(e.target.value, wordsOf(s.when)) })}>
            {KINDS.map(([k, t]) => <option key={k} value={k}>{t}</option>)}
          </select>
          {(kind === "needs" || kind === "says") && (
            <input className="input" value={wordsOf(s.when)} aria-label={kind === "needs" ? "what the task needs" : "the words"} data-testid="flow-step-words"
                   placeholder={kind === "needs" ? "pdf, images, audio, video, code, review" : "fix, implement"}
                   onChange={(e) => setStep(i, { when: whenFrom(kind, e.target.value) })} />
          )}
        </label>
        <div className="cw-field"><span className="cw-label mono">Repeat until</span><Repeat s={s} i={i} /></div>
      </div>
      {notes.map((c) => <div key={c.id} className="fl-note" data-testid="flow-step-ghost-note">the builder would: {c.summary}</div>)}
    </div>
  );
}

export function GhostStep({ c, n }: { c: Change; n: number }) {
  const s = c.ghost?.step;
  if (!s) return null;
  return (
    <div className="fl-step" data-ghost="1" data-testid="flow-ghost-step" title={c.summary}>
      <div className="fl-step-top"><span className="fl-n mono">NEW STEP {n}</span><b>{s.name}</b>
        <span className="cw-line">(the builder's proposal: Apply or Discard below)</span></div>
      <div className="fl-chips">{s.agents.map((a) => <span key={a} className="fl-chip"><span className="fl-chip-name">{a}</span></span>)}</div>
      <div className="cw-line">{c.summary.split(": ").slice(1).join(": ")}</div>
    </div>
  );
}
