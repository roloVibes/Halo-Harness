// The Steward page's model picker (3.3.7.0 R5; ollama_steward/candidates.py): the models that could run the steward
// here, best first, each with why -- fits beside the main model, its size, tool calls verified -- and Use (writes
// ollama.steward.model). A known-good small model to download shows only when nothing installed fits; its button is
// Local -> Library's Download and verify. `halo ollama steward candidates` prints the same.
import { useEffect } from "react";
import { Button } from "../../lib/ui";
import { loadCandidates, pick, useChat } from "./chatstore";

export function StewardModel() {
  const cands = useChat((s) => s.cands);
  const chosen = useChat((s) => s.chosen);
  useEffect(() => {
    void loadCandidates();
  }, []);
  return (
    <details className="lc-block" data-testid="steward-model" open={!chosen}>
      <summary className="rail-label mono">THE STEWARD'S MODEL · {chosen || "none chosen"}</summary>
      <ul className="lc-model-list">
        {(cands || []).map((c) => (
          <li key={c.model} className="lc-adv-row" data-testid="steward-candidate" data-ref={c.ref} data-installed={c.installed || undefined}>
            <div className="lc-adv-head">
              <span className="mono">{c.model}</span>
              {c.ref === chosen && <span className="og-chip mono">in use</span>}
              <span className="muted lc-adv-says">{c.why}</span>
            </div>
            {c.installed && c.ref !== chosen && (
              <Button size="sm" variant="ghost" onClick={() => void pick(c.ref)} data-testid="steward-candidate-use"
                      title={`ollama.steward.model = ${c.ref}`}>Use</Button>
            )}
            {!c.installed && (
              <code className="mono lc-cli-line">{`halo models pull ${c.model.slice(3).split("@")[0]} --host ${c.host}`}</code>
            )}
          </li>
        ))}
      </ul>
      {cands && !cands.length && <p className="muted">No local model here could run the steward yet.</p>}
    </details>
  );
}
