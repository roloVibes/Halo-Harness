// The recall box (3.1.8.0 R4, docs/RECALL.md; its route is 3.1.2.0 R3's
// `GET /api/recall?q=&k=8[&fleet=1]`, studio/recall_api.py): what this
// harness remembers -- memory topics, past sessions, the coach library,
// findings, decisions and your own notes -- ranked for some words by the
// local embedding model; with Fleet on, every online harness answers from
// its own index and the hits merge by score. Each hit shows its kind's chip,
// its title, score and excerpt, its harness (Fleet), and a finding or a
// decision its id, who wrote it, the day and its confidence. A harness that
// did not answer gets one line saying why. Shown under "Who can..." in the
// Capabilities panel's full face.
import { useEffect, useState } from "react";
import { api } from "../../lib/api";
import { Icon } from "../../lib/ui";

type Hit = { score: number; title: string; kind: string; excerpt?: string; harness?: string; ref?: string; by?: string; when?: string; confidence?: string };
type Row = { harness: string; name: string; local?: boolean; state: string; hits: number; note?: string };
type Answer = { query: string; fleet: boolean; hits: Hit[]; harnesses: Row[] };

const CHIP: Record<string, string> = { memory: "memo", session: "sess", coach_library: "lib", finding: "finding", decision: "decision", note: "note" };

function HitRow({ h, fleet }: { h: Hit; fleet: boolean }) {
  const meta = [h.ref, h.by && `by ${h.by}`, h.when && h.when.slice(0, 10), h.confidence].filter(Boolean).join(" · ");
  return (
    <li className="frec-row" data-testid="fleet-recall-hit" data-kind={h.kind}>
      <span className="og-chip mono" data-kind={h.kind}>{CHIP[h.kind] || h.kind}</span>
      <b className="frec-title">{h.title}</b>
      <span className="mono frec-score" title="similarity to your words">{h.score.toFixed(3)}</span>
      {meta && <span className="mono muted frec-meta" data-testid="fleet-recall-meta">{meta}</span>}
      {fleet && h.harness && <span className="mono muted frec-meta">on {h.harness}</span>}
      {h.excerpt && <p className="frec-excerpt muted">{h.excerpt}</p>}
    </li>
  );
}

export function RecallBox() {
  const [text, setText] = useState("");
  const [fleet, setFleet] = useState(false);
  const [busy, setBusy] = useState(false);
  const [out, setOut] = useState<Answer | null>(null);
  const [error, setError] = useState("");
  useEffect(() => {
    const q = text.trim();
    if (!q) {
      setOut(null);
      setError("");
      return;
    }
    let live = true;
    const id = window.setTimeout(() => {
      setBusy(true);
      api.get<Answer>("recall", { q, k: 8, fleet: fleet ? 1 : undefined })
        .then((a) => {
          if (live) {
            setOut(a);
            setError("");
          }
        })
        .catch((e) => {
          if (live) {
            setOut(null);
            setError(e instanceof Error ? e.message : String(e));
          }
        })
        .finally(() => {
          if (live) setBusy(false);
        });
    }, 300);
    return () => {
      live = false;
      window.clearTimeout(id);
    };
  }, [text, fleet]);
  const quiet = (out?.harnesses || []).filter((r) => r.state !== "answered" || r.note);
  return (
    <section className="frec" data-testid="fleet-recall">
      <div className="fwho-box">
        <Icon name="search" />
        <input value={text} onChange={(e) => setText(e.target.value)} placeholder="Recall... (memory, sessions, findings, decisions, your notes)"
               aria-label="Recall" data-testid="fleet-recall-input" spellCheck={false} />
        {busy && <span className="mono muted">recalling...</span>}
        <button className="frec-fleet mono" aria-pressed={fleet} data-testid="fleet-recall-fleet" onClick={() => setFleet(!fleet)}
                title="ask every online harness of the fleet; each answers from its own index, only the hits leave a box">
          Fleet
        </button>
      </div>
      {error && <p className="fwho-none muted">{error}</p>}
      {out && !error && (out.hits.length
        ? <ol className="frec-list" data-testid="fleet-recall-results">{out.hits.map((h, i) => <HitRow key={`${h.harness}-${h.title}-${i}`} h={h} fleet={out.fleet} />)}</ol>
        : <p className="fwho-none muted" data-testid="fleet-recall-none">Nothing recalled for "{out.query}".</p>)}
      {quiet.map((r) => <p key={r.harness || r.name} className="frec-note muted mono">{r.name}: {r.state}{r.note ? ` -- ${r.note}` : ""}</p>)}
    </section>
  );
}
