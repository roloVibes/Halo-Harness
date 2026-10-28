// The Ollama panel's models table (3.3.4.0 R5): one row per model a host served or was asked for (the ledger's
// last 24 h, what /api/ps has loaded now, a profile here): loaded now with its VRAM share and when it unloads,
// the last hour's calls / trims / cuts / reloads / errors, the p95 prompt against the window sent, the
// profile's window and reply reserve and who set them, and the eye for a vision model. A Hugging Face local
// server's rows come from its OpenAI-dialect ledger lines, labelled "local server". 3.3.5.0 R0: each row's
// window and its source (agent/model_window.py). 3.3.5.0 R0b: each row's card chips (think, tools, vision,
// the purpose, the window), the fit meter on this host's card, and the card's how lines (shared/ModelCard.tsx).
import { FitMeter, Icon } from "../../lib/ui";
import { CardChips, CardDetail } from "../shared/ModelCard";
import { byWho, gib, k, type HostView, type ModelRow } from "./ostore";

function until(iso: string | null): string {
  if (!iso) return "";
  const s = Math.round((Date.parse(iso) - Date.now()) / 1000);
  if (!Number.isFinite(s)) return "";
  if (s <= 0) return "unloading";
  return s < 120 ? `unloads in ${s}s` : `unloads in ${Math.round(s / 60)}m`;
}

function Loaded({ m }: { m: ModelRow }) {
  const l = m.loaded;
  if (!l) return <span className="muted">not loaded</span>;
  const spill = typeof l.vram_pct === "number" && l.vram_pct < 100;
  return (
    <span className="oll-loaded" data-spill={spill || undefined} title={`${gib(l.size_vram)} of ${gib(l.size)} on the GPU`}>
      <span className="oll-vram" aria-hidden="true">
        <span style={{ width: `${Math.min(100, l.vram_pct ?? 0)}%` }} />
      </span>
      <span className="mono" data-testid="ollama-vram">{l.vram_pct ?? "?"}% VRAM</span>
      {l.context_length ? <span className="mono muted"> at {k(l.context_length)}</span> : null}
      <span className="muted"> {until(l.expires)}</span>
    </span>
  );
}

function Window({ m }: { m: ModelRow }) {
  const h = m.hour;
  if (!h || h.p95_prompt == null) return <span className="muted">no prompts this hour</span>;
  const tight = typeof h.p95_pct === "number" && h.p95_pct >= 90;
  return (
    <span className="mono" data-tight={tight || undefined} title="the 95th percentile prompt against the window sent">
      p95 {k(h.p95_prompt)}{h.window ? ` of ${k(h.window)}` : ""}{h.p95_pct != null ? ` (${Math.round(h.p95_pct)}%)` : ""}
    </span>
  );
}

/** 3.3.5.0 R0: the model's window here and where the number came from (the profile, the learned cap, the trained context ...). */
function ModelWindow({ m }: { m: ModelRow }) {
  const w = m.window;
  if (!w || !w.tokens) return null;
  return (
    <span className="mono muted" data-testid="ollama-model-window" data-source={w.source}
          title={`the window a switch to this model fits to${w.ceiling ? `; the most it can get here: ${w.ceiling.toLocaleString("en-US")}` : ""}`}>
      window {w.tokens.toLocaleString("en-US")} ({w.source})
    </span>
  );
}

function Profile({ m }: { m: ModelRow }) {
  const p = m.profile;
  if (!p || (p.num_ctx == null && p.num_predict == null && p.keep_alive == null)) return <span className="muted">no profile</span>;
  const n = (v: number) => v.toLocaleString("en-US"); // a window is an exact number of tokens
  const parts = [p.num_ctx != null ? `window ${n(p.num_ctx)}` : "", p.num_predict != null ? `reserve ${n(p.num_predict)}` : "",
                 p.keep_alive != null ? `keep-alive ${p.keep_alive}` : ""].filter(Boolean);
  return (
    <span className="mono" title={p.note || ""} data-testid="ollama-profile">
      {parts.join(" · ")} <span className="og-chip mono" data-by={p.by || "user"}>{byWho(p.by)}</span>
    </span>
  );
}

function Row({ m, local }: { m: ModelRow; local: boolean }) {
  const h = m.hour;
  const n = (v: number | undefined, label: string) => (
    <span className="oll-n mono" data-n={label} data-hot={(v || 0) > 0 && label !== "calls" ? true : undefined}>
      {v ?? 0} <span className="muted">{label}</span>
    </span>
  );
  return (
    <li className="oll-model" data-testid="ollama-model-row" data-model={m.model} data-calls={h?.calls ?? 0} data-trims={h?.trims ?? 0}
        data-cuts={h?.cuts ?? 0} data-errors={h?.errors ?? 0} data-reloads={h?.reloads ?? 0}>
      <div className="oll-model-top">
        <b className="mono">{m.model}</b>
        {m.vision && <span className="oll-eye" title="this model reads images" data-testid="ollama-vision"><Icon name="eye" size={12} label="vision" /></span>}
        {local && <span className="og-chip mono">local server</span>}
        <CardChips card={m.card} />
        <FitMeter fit={m.fit} />
        <span className="spacer" />
        {!local && <Loaded m={m} />}
      </div>
      <div className="oll-model-nums">
        {n(h?.calls, "calls")}
        {n(h?.trims, "trims")}
        {n(h?.cuts, "cuts")}
        {n(h?.reloads, "reloads")}
        {n(h?.errors, "errors")}
        <span className="muted mono">· {m.day_calls} in 24 h</span>
      </div>
      <div className="oll-model-fit">
        <Window m={m} />
        <ModelWindow m={m} />
        <span className="spacer" />
        <Profile m={m} />
      </div>
      <CardDetail card={m.card} refName={m.model} />
    </li>
  );
}

export function ModelsTable({ host }: { host: HostView }) {
  const local = host.kind === "local server";
  if (!host.models.length)
    return <p className="muted oll-empty">No calls to {host.name} in the last 24 hours and nothing loaded: the rows fill in as halos call it.</p>;
  return (
    <section className="oll-block" aria-label="Models">
      <div className="rail-label mono">MODELS · THE LAST HOUR</div>
      <ul className="oll-models">
        {host.models.map((m) => (
          <Row key={m.model} m={m} local={local} />
        ))}
      </ul>
      {local && <p className="muted oll-next">The rest of Hugging Face (the Hub, endpoints, pulling a model): next, the Models section (3.3.5.0).</p>}
    </section>
  );
}
