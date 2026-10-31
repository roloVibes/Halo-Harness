// The filters under a chevron on Local -> Library (3.3.6.0 R2; plans/local-model-fit-brief.md F2), in three groups:
// Role & capability (each capability at the truth it needs: verified, verified or declared, expected, any -- "any"
// also keeps a model that needs a probe), Fit & resources (fully on the GPU, co-resides with, quant, params, disk,
// speed, cold load, KV per token; "fits this host" and the window stay on top) and Supply, licence, platform
// (licence class, gated, source, runs here, this Ollama loads it, freshness, exclude crashed; the family, quant and
// licence words of 3.3.5.0 R2 too). Every change reads the list again against the resource strip.
import { editBundle, setFilters, useLib } from "./libstore";

const CAPS = ["tools", "thinking", "coder", "agentic-ready", "planner", "verifier", "compactor", "bulk", "abliterated", "vision",
              "audio", "embedding", "security", "math", "multilingual", "long-context", "tool-accuracy"];
// 3.3.6.0 R6: the vision need reads the one vision fact (providers/vision_fact.py), the same the eye chip shows
const VISION_TITLE = "can see images: verified by the battery's image probe, declared by the server or the catalog, or " +
  "expected from the family; the weakest truth it may have";
const FIT: [string, string, string][] = [["quant_max", "quant ≤", "Q4"], ["params_max", "params ≤ B", "14"],
  ["speed_min", "tok/s ≥", "50"], ["cold_load_max_s", "cold load ≤ s", "30"], ["kv_efficiency", "KV ≤ KB/token", "48"],
  ["co_resides_with", "co-resides with", "qwen3.5:9b"]];
const TRI: [string, string][] = [["", "any"], ["yes", "yes"], ["no", "no"]];

function Num({ part, k, label, ph }: { part: "fitf" | "supply"; k: string; label: string; ph: string }) {
  const v = useLib((s) => (s.filters[part] as Record<string, string | boolean>)[k]);
  return (
    <label>
      {label}{" "}
      <input className="lc-lib-word" value={typeof v === "string" ? v : ""} placeholder={ph} data-testid="local-filter" data-key={k}
             onChange={(e) => editBundle(part, k, e.target.value || null, true)} aria-label={label} />
    </label>
  );
}

function Check({ part, k, label, title }: { part: "fitf" | "supply"; k: string; label: string; title: string }) {
  const v = useLib((s) => (s.filters[part] as Record<string, string | boolean>)[k]);
  return (
    <label className="lc-lib-check" title={title}>
      <input type="checkbox" checked={v === true || v === "1"} onChange={(e) => editBundle(part, k, e.target.checked || null)}
             data-testid="local-filter" data-key={k} /> {label}
    </label>
  );
}

function Tri({ k, label }: { k: string; label: string }) {
  const v = useLib((s) => s.filters.supply[k]);
  const cur = v === true || v === "yes" ? "yes" : v === "no" ? "no" : "";
  return (
    <label>
      {label}{" "}
      <select value={cur} onChange={(e) => editBundle("supply", k, e.target.value || null)} data-testid="local-filter" data-key={k}>
        {TRI.map(([id, w]) => <option key={id} value={id}>{w}</option>)}
      </select>
    </label>
  );
}

export function SearchFilters() {
  const f = useLib((s) => s.filters);
  return (
    <details className="ls-more" data-testid="local-library-more">
      <summary className="mono">filters: role and capability · fit and resources · supply, licence, platform</summary>
      <div className="ls-group" data-testid="local-filter-group" data-group="capability">
        <div className="rail-label mono">ROLE &amp; CAPABILITY</div>
        <div className="lc-lib-line mono">
          {CAPS.map((c) => (
            <label key={c} title={c === "vision" ? VISION_TITLE : "the weakest truth it may have"}>
              {c === "vision" ? "can see images" : c}{" "}
              <select value={f.need[c] || ""} onChange={(e) => editBundle("need", c, e.target.value || null)} data-testid="local-need" data-cap={c}>
                <option value="">-</option>
                <option value="verified">verified</option>
                <option value="declared">verified or declared</option>
                <option value="expected">expected</option>
                <option value="any">any (also not probed)</option>
              </select>
            </label>
          ))}
        </div>
      </div>
      <div className="ls-group" data-testid="local-filter-group" data-group="fit">
        <div className="rail-label mono">FIT &amp; RESOURCES</div>
        <div className="lc-lib-line mono">
          <Check part="fitf" k="fits_at" label="fits at the window" title="weights + KV at the window + overhead within the usable VRAM" />
          <Check part="fitf" k="fully_on_gpu" label="fully on the GPU" title="no CPU spill at the window" />
          {FIT.map(([k, label, ph]) => <Num key={k} part="fitf" k={k} label={label} ph={ph} />)}
          <label title="at most this many GB on disk">
            disk ≤{" "}
            <input className="lc-lib-num" inputMode="decimal" value={f.max_gb} placeholder="GB" onChange={(e) => setFilters({ max_gb: e.target.value }, true)}
                   data-testid="local-library-maxgb" aria-label="At most this many GB" />
          </label>
        </div>
      </div>
      <div className="ls-group" data-testid="local-filter-group" data-group="supply">
        <div className="rail-label mono">SUPPLY, LICENCE, PLATFORM</div>
        <div className="lc-lib-line mono">
          <label>
            licence{" "}
            <select value={String(f.supply.licence || "")} onChange={(e) => editBundle("supply", "licence", e.target.value || null)} data-testid="local-filter" data-key="licence">
              {["", "permissive", "restricted", "research", "known", "unknown"].map((x) => <option key={x} value={x}>{x || "any"}</option>)}
            </select>
          </label>
          <Tri k="gated" label="gated on the hub" />
          <label>
            source{" "}
            <select value={String(f.supply.kind || "")} onChange={(e) => editBundle("supply", "kind", e.target.value || null)} data-testid="local-filter" data-key="kind">
              {[["", "any"], ["ollama", "Ollama library"], ["hf-gguf", "HF GGUF"], ["mlx", "MLX"]].map(([id, w]) => <option key={id} value={id}>{w}</option>)}
            </select>
          </label>
          <Check part="supply" k="runs_here" label="runs on this OS + GPU" title="MLX on a Mac only; CUDA on NVIDIA; ROCm / Vulkan on AMD" />
          <Check part="supply" k="ollama_supports" label="this Ollama loads it" title="its architecture against the host's Ollama version" />
          <Num part="supply" k="fresh_within_months" label="updated within months" ph="6" />
          <label className="lc-lib-check" title="grey the models that crashed on this host and put them last (halo ollama crashes)">
            <input type="checkbox" checked={f.exclude_crashed} onChange={(e) => setFilters({ exclude_crashed: e.target.checked })}
                   data-testid="local-exclude-crashed" /> exclude: crashed on this host
          </label>
          <label>
            family <input className="lc-lib-word" value={f.family} onChange={(e) => setFilters({ family: e.target.value }, true)} data-testid="local-library-family" aria-label="Family" />
          </label>
          <label>
            quant <input className="lc-lib-word" value={f.quant} placeholder="Q4_K_M" onChange={(e) => setFilters({ quant: e.target.value }, true)} data-testid="local-library-quant" aria-label="Quantization" />
          </label>
          <label>
            licence word <input className="lc-lib-word" value={f.license} onChange={(e) => setFilters({ license: e.target.value }, true)} data-testid="local-library-license" aria-label="Licence" />
          </label>
        </div>
      </div>
    </details>
  );
}
