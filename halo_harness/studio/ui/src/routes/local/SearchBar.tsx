// The top of Local -> Library (3.3.6.0 R2): the resource strip pinned (host, GPU, usable / free VRAM, disk free,
// resident models: every filter is worked out against it and reads again when the host or the window moves), the
// preset buttons (Coder, Reasoner / planner, Bulk worker, Compactor, Verifier, Security / pentest, Multimodal,
// Embeddings, Offline-only), and the bundle of the preset on show, expanded and editable -- each need at its truth
// floor, each fit and supply value removable -- with Save as role template (a `local-<preset>` lineup).
import { Button } from "../../lib/ui";
import { applyPreset, editBundle, useLib } from "./libstore";
import type { Bundle, Strip } from "./types";
import { saveTemplate, useVerify } from "./verify";

const FLOORS = ["verified", "declared", "expected", "any"];
const gb = (n: number | null | undefined) => (typeof n === "number" ? `${(n / 2 ** 30).toFixed(1)} GB` : "?");

export function ResourceLine({ s }: { s?: Strip }) {
  if (!s) return null;
  if (!s.card) return <p className="mono muted ls-strip" data-testid="local-resource-strip" data-card="no">{s.line}</p>;
  const res = (s.resident || []).map((r) => `${r.model} ${gb(r.bytes)}`).join(", ") || "nothing";
  return (
    <div className="ls-strip mono" data-testid="local-resource-strip" data-card="yes" data-host={s.host || ""} data-free={s.free ?? ""}
         data-window={s.window} aria-label="the host every row is worked out on">
      <b>{s.host}</b>
      <span title="the GPU on the hardware card">{s.gpu}</span>
      <span title={`what models may hold: the card minus other programs (${gb(s.others)}); KV cache ${s.kv}`}>usable {gb(s.usable)}</span>
      <span data-testid="local-strip-free" title="usable minus the resident models">free {gb(s.free)}</span>
      <span title={s.disk_from || ""}>disk free {gb(s.disk_free ?? undefined)}</span>
      <span title="loaded now (/api/ps)">resident: {res}</span>
      <span title="the window every fit is worked out at">at {s.window.toLocaleString("en-US")}</span>
      {s.version && <span title="the host's Ollama version">Ollama {s.version}</span>}
    </div>
  );
}

function Pairs({ part, rows }: { part: "fitf" | "supply"; rows: Record<string, unknown> }) {
  const keys = Object.keys(rows || {});
  if (!keys.length) return null;
  return (
    <>
      {keys.map((k) => (
        <span key={k} className="og-chip mono ls-pair" data-testid="local-bundle-pair" data-key={k}>
          {k.replace(/_/g, " ")}{rows[k] === true ? "" : `: ${String(rows[k])}`}
          <button type="button" className="ls-x" onClick={() => editBundle(part, k, null)} aria-label={`remove ${k}`} title={`remove ${k}`}>×</button>
        </span>
      ))}
    </>
  );
}

function BundleView({ b }: { b: Bundle }) {
  const f = useLib((s) => s.filters);
  const saved = useVerify((s) => s.said[`t|${b.id}`]);
  const needs = f.edited ? f.need : b.needs;
  const fit = f.edited ? f.fitf : b.fit;
  const supply = f.edited ? f.supply : b.supply;
  const understood = useLib((s) => s.data?.search?.understood || []);
  return (
    <section className="ls-bundle" data-testid="local-preset-bundle" data-preset={b.id} aria-label={`${b.title}: its filters`}>
      <div className="mono"><b>{b.title || "Search"}</b> <span className="muted">{b.why}</span></div>
      {understood.length > 0 && <div className="mono muted" data-testid="local-bundle-understood">understood: {understood.join(" · ")}</div>}
      <div className="ls-needs">
        {Object.entries(needs).map(([cap, floor]) => (
          <label key={cap} className="mono ls-need" data-testid="local-bundle-need" data-cap={cap} data-floor={floor}
                 title="the weakest truth this capability may have: verified (probed here), declared (metadata), expected (the family or name), any (also not probed)">
            {cap}{" "}
            <select value={floor} onChange={(e) => editBundle("need", cap, e.target.value)} aria-label={`${cap}: the truth it needs`}>
              {FLOORS.map((x) => <option key={x} value={x}>{x === "declared" ? "verified or declared" : x}</option>)}
            </select>
            <button type="button" className="ls-x" onClick={() => editBundle("need", cap, null)} aria-label={`drop ${cap}`} title={`drop ${cap}`}>×</button>
          </label>
        ))}
        <Pairs part="fitf" rows={fit as Record<string, unknown>} />
        <Pairs part="supply" rows={supply as Record<string, unknown>} />
      </div>
      {b.id && (
        <div className="ls-save">
          <Button size="sm" onClick={() => void saveTemplate(b.id, { needs, fit, supply })} data-testid="local-save-template"
                  title={`write these filters as the lineup local-${b.id} (main and the ${b.lineup_role || "search"} role; not active until halo teams apply)`}>
            Save as role template
          </Button>
          {saved && <span className="mono lc-said" data-ok={saved.ok || undefined} data-testid="local-save-template-said">{saved.text}</span>}
        </div>
      )}
    </section>
  );
}

export function SearchBar() {
  const data = useLib((s) => s.data);
  const preset = useLib((s) => s.filters.preset);
  const forRole = useLib((s) => s.filters.for_role);
  const bundle = data?.search?.bundle || null;
  return (
    <div className="ls-top" data-testid="local-search-top">
      <ResourceLine s={data?.strip} />
      <div className="lc-intents" role="group" aria-label="Find a model for a role" data-testid="local-presets">
        <span className="mono muted">find a:</span>
        {(data?.presets || []).map((b) => (
          <button key={b.id} type="button" className={"lc-intent" + ((data?.search?.preset || preset) === b.id ? " on" : "")}
                  aria-pressed={(data?.search?.preset || preset) === b.id} title={b.why} data-testid="local-preset" data-preset={b.id}
                  onClick={() => applyPreset((data?.search?.preset || preset) === b.id ? null : b)}>
            {b.title}
          </button>
        ))}
        {forRole && <span className="mono muted" data-testid="local-for-role">for the role {forRole}</span>}
      </div>
      {bundle && (bundle.id || Object.keys(bundle.needs).length > 0) && <BundleView b={bundle} />}
    </div>
  );
}
