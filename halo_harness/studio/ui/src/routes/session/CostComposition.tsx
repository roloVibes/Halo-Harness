// What the session's last request was made of (3.3.5.0 R4, the prompt budget):
// one stacked bar of its parts in tokens -- Halo's own system prompt and
// CLAUDE.md, the memory (MEMORY.md), the topic index, the tool schemas, the
// history and what you typed -- from the session row's `composition`
// (agent/prompt_composition.ledger_fields through the status event), each part
// in its own token colour with its count beside it. The same line `/cost` and
// `/status` print. Nothing shows before the session's first request.
import type { Composition } from "../fleet/types";
import { tok } from "./CostParts";

export const PARTS: { key: keyof Composition; label: string; what: string }[] = [
  { key: "system", label: "system", what: "Halo's own system prompt, its snapshots and CLAUDE.md" },
  { key: "memory", label: "memory", what: "MEMORY.md (auto-loaded), sent once" },
  { key: "topic_index", label: "topics", what: "the memory's topic index (one line per topic file on a lean prompt)" },
  { key: "tools_schema", label: "tools", what: "the tool schemas offered to the model" },
  { key: "history", label: "history", what: "the conversation so far, tool output included" },
  { key: "user", label: "you", what: "what you typed in the last turn, and its attachments" },
];

export function CompositionBar({ c }: { c: Composition | null | undefined }) {
  if (!c || !c.total) return null;
  const total = Math.max(1, Number(c.total) || 0);
  const parts = PARTS.map((p) => ({ ...p, n: Math.max(0, Number(c[p.key]) || 0) }));
  const line = parts.map((p) => `${p.label} ${p.n.toLocaleString("en-US")}`).join(" · ");
  return (
    <section className="sco-comp" data-testid="session-cost-composition" data-total={c.total}
             title={`prompt ${Number(c.total).toLocaleString("en-US")}: ${line}`}>
      <div className="sco-comp-head">
        <span className="sco-label mono">LAST PROMPT</span>
        <b className="mono" data-testid="session-cost-composition-total">{tok(c.total)}</b>
        <span className="mono muted">tokens, by part</span>
      </div>
      <div className="sco-comp-bar" aria-hidden="true">
        {parts.filter((p) => p.n > 0).map((p) => (
          <span key={p.key} className="sco-comp-seg" data-part={p.key} data-testid="session-cost-composition-seg"
                style={{ flexGrow: p.n / total }} title={`${p.label}: ${p.n.toLocaleString("en-US")} tokens (${p.what})`} />
        ))}
      </div>
      <div className="sco-comp-keys mono">
        {parts.map((p) => (
          <span key={p.key} className="sco-comp-key" data-part={p.key} data-n={p.n} title={p.what}>
            <i className="sco-comp-dot" data-part={p.key} /> {p.label} {tok(p.n)}
          </span>
        ))}
      </div>
    </section>
  );
}
