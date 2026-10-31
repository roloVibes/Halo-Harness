// "Why this answer?" (3.3.6.0 R4; agent/postmortem.py, studio/postmortem_api.py): a Live row's "why?" button asks
// GET sessions/<sid>/postmortem?at=<the row's time>&agent=<its agent> and opens the Inspector on the Live panel,
// where WhySettings shows it -- one plain line (the prompt cut, memory-dominated, thinking only, no tools, an empty
// reply from a small budget, the cache) and the details beneath. No pop-up: the inspector shows it, Esc closes it.
import { api, ApiError } from "../../lib/api";
import { createStore, studio, useStore } from "../../lib/store";
import { parseKey } from "../fleet/store";
import type { LiveLine } from "../shared/liveFeed";

export type WhyAnswer = { ok: boolean; line: string; details: string[]; turn: number | null; model?: string; host?: string; cli?: string };
type WhyState = { key: string; n: number; busy: boolean; answer: WhyAnswer | null; error: string };
export const why = createStore<WhyState>({ key: "", n: -1, busy: false, answer: null, error: "" });

export async function askWhy(l: LiveLine): Promise<void> {
  const { s, a } = parseKey(l.key);
  why.update(() => ({ key: l.key, n: l.n, busy: true, answer: null, error: "" }));
  studio.update(() => ({ inspector: { section: "session", panel: "session-live" } }));
  try {
    const q: Record<string, string> = { at: String(l.ts) };
    if (a && a !== "main") q.agent = a;
    const answer = await api.get<WhyAnswer>(`sessions/${encodeURIComponent(s)}/postmortem`, q);
    why.update(() => ({ busy: false, answer }));
  } catch (e) {
    why.update(() => ({ busy: false, error: e instanceof ApiError ? e.message : String(e) }));
  }
}

export function WhyButton({ l }: { l: LiveLine }) {
  const on = useStore(why, (w) => w.n === l.n && w.key === l.key);
  return (
    <button type="button" className="slv-why mono" data-testid="session-live-why" aria-pressed={on}
            onClick={() => void askWhy(l)} title="Why this answer? What the model saw for this turn (the Inspector shows it)">
      why?
    </button>
  );
}

export function WhySettings() {
  const w = useStore(why, (x) => x);
  if (!w.key) return <p className="muted">A Live row's <span className="mono">why?</span> shows here what the model saw for that turn.</p>;
  if (w.busy) return <p className="mono muted">reading the ledger and the log…</p>;
  if (w.error) return <p className="mono lc-said" data-testid="session-why-error">{w.error}</p>;
  const a = w.answer;
  if (!a) return null;
  return (
    <div className="session-why" data-testid="session-why" data-ok={a.ok || undefined}>
      <div className="rail-label mono">WHY THIS ANSWER{a.turn != null ? ` · TURN ${a.turn}` : ""}</div>
      <p className="session-why-line" data-testid="session-why-line">{a.line}</p>
      <ul className="mono muted session-why-details">
        {a.details.map((d) => <li key={d}>{d}</li>)}
      </ul>
      {a.cli && <code className="mono lc-cli-line" title="the same from a terminal">{a.cli}</code>}
    </div>
  );
}
