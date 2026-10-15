// "Who can..." (3.0.6.0 R6): one box, the fleet ranked for it. The ranking
// is computed in code on the hub (`GET fleet/who?q=`): an exact name beats a
// word of a name, which beats a word of a description; a tag the owner set
// counts double. Each result says what matched and why; clicking one picks
// that harness (its spec card opens, its box on the map lights up). `compact`
// (the panel's compact face): one line per result, the best three.
import { useEffect, useRef, useState } from "react";
import { Icon } from "../../lib/ui";
import { focusHarness, runWho, useCaps, type WhoRow } from "./caps";

const KIND: Record<string, string> = { mcp_tool: "MCP", skill: "skill", tag: "tag", model: "model", craft_app: "app", cli: "CLI", hardware: "hardware" };
const SAMPLES = ["gridcraft", "a 4090", "make a video", "pdf forms", "docker"];

function Result({ r, rank, best, compact }: { r: WhoRow; rank: number; best: number; compact: boolean }) {
  const focus = useCaps((s) => s.focus);
  return (
    <li>
      <button className="fwho-row" data-testid="fleet-who-result" data-id={r.harness} data-rank={rank} aria-pressed={focus === r.harness}
              onClick={() => focusHarness(r.harness)} title="pick this harness: its spec card opens and its box lights on the map">
        <span className="fwho-rank mono">{rank}</span>
        <b className="fwho-name">{r.name}</b>
        <span className="fwho-meter" aria-hidden="true"><i style={{ width: `${Math.max(6, Math.round((100 * r.score) / (best || 1)))}%` }} /></span>
        <span className="mono fwho-score" title="the sum of its five best matches">{r.score}</span>
        <ul className="fwho-why" data-compact={compact || undefined}>
          {r.matches.slice(0, compact ? 1 : 3).map((m) => (
            <li key={m.kind + m.name}><span className="og-chip mono" data-kind={m.kind}>{KIND[m.kind] || m.kind}</span> <span className="mono">{m.name}</span> <span className="muted">{m.why}</span></li>
          ))}
          {!compact && r.matched > 3 && <li className="muted">+{r.matched - 3} more match{r.matched - 3 === 1 ? "" : "es"}</li>}
        </ul>
      </button>
    </li>
  );
}

export function WhoBox({ autoFocus = false, compact = false }: { autoFocus?: boolean; compact?: boolean }) {
  const q = useCaps((s) => s.q);
  const who = useCaps((s) => s.who);
  const busy = useCaps((s) => s.whoBusy);
  const error = useCaps((s) => s.whoError);
  const [text, setText] = useState(q);
  const ref = useRef<HTMLInputElement>(null);
  useEffect(() => setText(q), [q]);
  useEffect(() => {
    if (autoFocus) ref.current?.focus();
  }, [autoFocus]);
  useEffect(() => {
    if (text === q) return;
    const id = window.setTimeout(() => void runWho(text), 250);
    return () => window.clearTimeout(id);
  }, [text, q]);
  const best = who?.[0]?.score || 1;
  return (
    <section className="fwho" data-testid="fleet-who" data-compact={compact || undefined}>
      <label className="fwho-box">
        <Icon name="search" />
        <input ref={ref} value={text} onChange={(e) => setText(e.target.value)} placeholder="Who can... (a tool, an app, a skill, a model, a GPU)"
               aria-label="Who can do this" data-testid="fleet-who-input" spellCheck={false} />
        {busy && <span className="mono muted">ranking...</span>}
      </label>
      {!q.trim() && !compact && (
        <div className="fwho-samples muted">
          try {SAMPLES.map((s) => <button key={s} className="fwho-sample mono" onClick={() => setText(s)}>{s}</button>)}
        </div>
      )}
      {error && <p className="fwho-none muted">{error}</p>}
      {who && !error && q.trim() && (who.length
        ? <ol className="fwho-list" data-testid="fleet-who-results">{who.slice(0, compact ? 3 : undefined).map((r, i) => <Result key={r.harness} r={r} rank={i + 1} best={best} compact={compact} />)}</ol>
        : <p className="fwho-none muted" data-testid="fleet-who-none">No harness lists anything that matches "{q.trim()}".</p>)}
    </section>
  );
}
