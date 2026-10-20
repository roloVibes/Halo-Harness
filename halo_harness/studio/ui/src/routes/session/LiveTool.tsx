// A tool call in the Live column (3.1.5.0 R3; 3.1.7.0 R1 "insight on the
// tool rows"): one row that reads like the Fleet log's ("runs Bash", what it
// runs on, the time ticking while it runs), then the first line of its result
// when it lands. A click on the row (Enter or Space with the focus on it)
// opens the whole result under it, up to the first 4000 characters, and
// closes it again; only rows with more than that first line open.
import { useState } from "react";
import { short } from "../orchestra/format";
import { useNow } from "../fleet/store";
import type { LiveLine } from "../shared/liveFeed";

/** 4s, 1m 05s. */
export function dur(ms: number): string {
  const s = Math.max(0, Math.round(ms / 1000));
  return s < 60 ? `${s}s` : `${Math.floor(s / 60)}m ${String(s % 60).padStart(2, "0")}s`;
}

export function ToolRow({ l }: { l: LiveLine }) {
  const now = useNow(!l.ended, 1000);
  const [open, setOpen] = useState(false);
  const took = l.ended && l.t0 && l.ended > l.t0 + 400 ? dur(l.ended - l.t0) : "";
  const more = !!l.full && l.full.trim() !== (l.result || "").trim();
  const toggle = () => more && setOpen((o) => !o);
  return (
    <div className="slv-tool" data-running={!l.ended || undefined} data-error={l.error || undefined} data-open={(more && open) || undefined} data-more={more || undefined}>
      <div className="slv-tool-head" data-testid="session-live-tool" onClick={toggle} role={more ? "button" : undefined} tabIndex={more ? 0 : undefined} aria-expanded={more ? open : undefined}
           onKeyDown={(e) => (e.key === "Enter" || e.key === " ") && more && (e.preventDefault(), e.stopPropagation(), toggle())}
           title={more ? (open ? "Close the result" : "Open the whole result") : undefined}>
        <span className="slv-runs">runs</span>
        <span className="slv-tool-name mono">{l.tool}</span>
        {l.target && <span className="slv-target mono" title={l.target}>{short(l.target, 90)}</span>}
        <span className="slv-elapsed mono" data-testid="session-live-elapsed">{l.ended ? took : dur(now - l.t0)}</span>
        {l.result !== undefined && (
          <div className="slv-result mono" data-testid="session-live-result">
            {more && <span className="slv-caret" aria-hidden="true">{open ? "▾ " : "▸ "}</span>}
            {l.error ? "✕ " : "→ "}{l.result}
          </div>
        )}
      </div>
      {more && open && <pre className="slv-full mono" data-testid="session-live-full">{l.full}</pre>}
    </div>
  );
}
