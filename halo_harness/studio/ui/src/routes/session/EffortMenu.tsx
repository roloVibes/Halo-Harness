// The session header's effort control (3.3.5.0 R0b (c); studio/model_card_api.py): the word the session
// sends (think on / think off / effort n/a / the cloud level) as a button; a click lists what effort can do
// on THIS model (GET models/effort): think on / off / default on a thinking local model (low / medium / high
// on gpt-oss), "no adjustable effort" on one whose effort does nothing, the route's levels on a cloud model
// (set there with /effort, since a level lives in the session). A think pick writes `models.think[ref]`
// (POST models/think), which the session reads on its next call; the word follows at once.
import { useState } from "react";
import { api } from "../../lib/api";

type Effort = { ref: string; kind: "think" | "none" | "levels"; options: string[]; word: string; choice: string | null };

export function EffortMenu({ model, word }: { model: string; word: string }) {
  const [open, setOpen] = useState(false);
  const [got, setGot] = useState<Effort | null>(null);
  const [now, setNow] = useState<{ word: string; for: string } | null>(null);
  const [error, setError] = useState("");
  const shown = now && now.for === word ? now.word : word;
  const toggle = async () => {
    if (open) {
      setOpen(false);
      return;
    }
    setOpen(true);
    setError("");
    try {
      setGot(await api.get<Effort>(`models/effort?ref=${encodeURIComponent(model)}`));
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  };
  const pick = async (value: string) => {
    try {
      const r = await api.post<Effort>("models/think", { ref: model, value });
      setGot(r);
      setNow({ word: r.word, for: word });
      setOpen(false);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  };
  return (
    <span className="sco-effort" data-testid="session-effort-control">
      <button type="button" className="og-link mono" onClick={() => void toggle()} aria-expanded={open} disabled={!model}
              data-testid="session-cost-effort" data-na={shown === "effort n/a" || undefined} title="what the effort level does on this model; click for its options">
        {shown}
      </button>
      {open && (
        <span className="sco-effort-menu mono" role="menu" data-testid="session-effort-menu" data-kind={got?.kind || ""}>
          {!got && !error && <span className="muted">reading...</span>}
          {got?.kind === "think" && got.options.map((o) => (
            <button key={o} type="button" role="menuitemradio" aria-checked={(got.choice || "default") === o} className="og-chip mono"
                    onClick={() => void pick(o)} data-testid="session-effort-option" data-value={o}>
              {o === "default" ? "default" : `think ${o}`}
            </button>
          ))}
          {got?.kind === "none" && <span className="muted" data-testid="session-effort-none">no adjustable effort on this model (the level is kept for the next model that can use it)</span>}
          {got?.kind === "levels" && <span className="muted">{got.options.join(" · ")}: set it in the session with /effort &lt;level&gt;</span>}
          {error && <span className="muted">{error}</span>}
        </span>
      )}
    </span>
  );
}
