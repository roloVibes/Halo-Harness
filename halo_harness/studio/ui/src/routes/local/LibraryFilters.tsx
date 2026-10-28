// Local -> Library's controls (3.3.5.0 R2): the search box, the source switch (Ollama / Hugging Face / both),
// the host picker and the window control (every row's fit badge follows both), the intent filter (R1's: code,
// chat, long documents, images, embed -- idea 3), and the filters: fits this host, size on disk, family,
// capability, quantization, licence. Each change reads the list again (libstore.setFilters).
import { setFilters, useLib, WINDOWS, type Filters } from "./libstore";
import type { LibraryAnswer } from "./types";

const SOURCES: [Filters["source"], string][] = [["all", "Both"], ["ollama", "Ollama"], ["hf", "Hugging Face"]];
const CAPS = ["tools", "vision", "thinking", "embedding"];

function windowsFor(data: LibraryAnswer | null): number[] {
  const extra = [data?.window, data?.host?.max_ctx].filter((n): n is number => typeof n === "number" && n > 0);
  return [...new Set([...WINDOWS, ...extra])].sort((a, b) => a - b);
}

export function LibraryFilters() {
  const f = useLib((s) => s.filters);
  const data = useLib((s) => s.data);
  const win = f.window || data?.window || 32768;
  return (
    <div className="lc-lib-filters" data-testid="local-library-filters">
      <div className="lc-lib-line">
        <input className="lc-lib-search mono" type="search" placeholder="search the library: qwen, coder, embed..." value={f.q}
               onChange={(e) => setFilters({ q: e.target.value }, true)} data-testid="local-library-search" aria-label="Search the library" />
        <span className="lc-lib-switch" role="group" aria-label="Which library" data-testid="local-library-source">
          {SOURCES.map(([id, title]) => (
            <button key={id} type="button" className={"lc-intent" + (f.source === id ? " on" : "")} aria-pressed={f.source === id}
                    onClick={() => setFilters({ source: id })} data-testid="local-library-source-btn" data-source={id}>
              {title}
            </button>
          ))}
        </span>
      </div>
      <div className="lc-lib-line mono">
        <label title="the Ollama host whose card the fit badge is worked out on">
          fit on{" "}
          <select value={f.host || data?.host?.name || ""} onChange={(e) => setFilters({ host: e.target.value })} data-testid="local-library-host">
            {(data?.hosts || []).map((h) => <option key={h.name} value={h.name}>{h.name}</option>)}
            {!(data?.hosts || []).length && <option value="">no Ollama host</option>}
          </select>
        </label>
        <label title="the window every fit badge is worked out at (default: the host's max_ctx, else 32,768)">
          at window{" "}
          <select value={win} onChange={(e) => setFilters({ window: Number(e.target.value) })} data-testid="local-library-window">
            {windowsFor(data).map((w) => <option key={w} value={w}>{w.toLocaleString("en-US")}</option>)}
          </select>
        </label>
        <label className="lc-lib-check" title="only the rows that fit this host at this window (fits or tight)">
          <input type="checkbox" checked={f.fits} onChange={(e) => setFilters({ fits: e.target.checked })} data-testid="local-library-fits" /> fits this host
        </label>
      </div>
      <div className="lc-intents" role="group" aria-label="What do you want a model for" data-testid="local-library-intents">
        <span className="mono muted">for:</span>
        <button type="button" className={"lc-intent" + (f.intent ? "" : " on")} onClick={() => setFilters({ intent: "" })}
                data-testid="local-library-intent" data-intent="">any</button>
        {(data?.intents || []).map((i) => (
          <button key={i.id} type="button" className={"lc-intent" + (f.intent === i.id ? " on" : "")} aria-pressed={f.intent === i.id}
                  onClick={() => setFilters({ intent: i.id })} data-testid="local-library-intent" data-intent={i.id}>
            {i.title}
          </button>
        ))}
      </div>
      <div className="lc-lib-line mono">
        <label>
          capability{" "}
          <select value={f.cap} onChange={(e) => setFilters({ cap: e.target.value })} data-testid="local-library-cap">
            <option value="">any</option>
            {CAPS.map((c) => <option key={c} value={c}>{c}</option>)}
          </select>
        </label>
        <label title="at most this many GB on disk">
          size ≤{" "}
          <input className="lc-lib-num" inputMode="decimal" value={f.max_gb} placeholder="GB" onChange={(e) => setFilters({ max_gb: e.target.value }, true)}
                 data-testid="local-library-maxgb" aria-label="At most this many GB" />
        </label>
        <label>
          family <input className="lc-lib-word" value={f.family} onChange={(e) => setFilters({ family: e.target.value }, true)} data-testid="local-library-family" aria-label="Family" />
        </label>
        <label>
          quant <input className="lc-lib-word" value={f.quant} placeholder="Q4_K_M" onChange={(e) => setFilters({ quant: e.target.value }, true)} data-testid="local-library-quant" aria-label="Quantization" />
        </label>
        <label>
          licence <input className="lc-lib-word" value={f.license} onChange={(e) => setFilters({ license: e.target.value }, true)} data-testid="local-library-license" aria-label="Licence" />
        </label>
      </div>
    </div>
  );
}
