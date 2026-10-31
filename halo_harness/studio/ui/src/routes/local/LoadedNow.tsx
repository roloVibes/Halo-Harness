// Loaded now, on top of Local -> Models (3.3.5.0 R3): every model a host has in memory (Ollama's /api/ps, through
// GET local/models), its share on the GPU, when it unloads, and Unload (keep_alive 0; the title is the
// `halo models unload` line). Nothing loaded: one line saying so.
// 3.3.6.0 R6: which loaded models can see -- each row's eye chip (shared/EyeChip.tsx) and the count in the header,
// so the model that sees is loaded before a screenshot is shared.
import { Button } from "../../lib/ui";
import { EyeChip, eyeOf } from "../shared/EyeChip";
import { line } from "./ctl";
import { gib, loadModels, unloadModel, useLocal } from "./store";
import type { ModelsAnswer } from "./types";

function until(iso: string | null): string {
  if (!iso) return "";
  const s = Math.round((Date.parse(iso) - Date.now()) / 1000);
  return !Number.isFinite(s) ? "" : s <= 0 ? "unloading" : s > 86400 * 30 ? "kept until unloaded" : s < 120 ? `unloads in ${s}s` : `unloads in ${Math.round(s / 60)}m`;
}

export function LoadedNow({ hosts }: { hosts: ModelsAnswer["hosts"] }) {
  const busy = useLocal((s) => !!s.busy);
  const cards = useLocal((s) => s.hosts);
  const rows = hosts.flatMap((h) => h.models.filter((m) => m.loaded).map((m) => ({ h: h.name, m })));
  const off = async (host: string, model: string) => {
    await unloadModel(host, model);
    void loadModels();
  };
  return (
    <section className="lc-block lc-loaded-now" aria-label="Loaded now" data-testid="local-loaded-now">
      <div className="rail-label mono">
        LOADED NOW · {rows.length}
        {rows.length > 0 && (
          <span data-testid="local-loaded-sees" title="loaded models that can see images (the eye chip on each row)">
            {" "}· {rows.filter(({ m }) => m.card?.vision === true).length} can see images
          </span>
        )}
      </div>
      {rows.length ? (
        <ul className="lc-loaded">
          {rows.map(({ h, m }) => {
            const l = m.loaded!;
            const pct = l.size && l.size_vram != null ? Math.round((100 * l.size_vram) / l.size) : null;
            const ctl = cards?.find((c) => c.name === h)?.controls;
            const why = ctl && !ctl.ok ? ctl.why : "";
            return (
              <li key={`${h}|${m.model}`} data-testid="local-loaded-row" data-host={h} data-model={m.model}>
                <span className="mono"><b>{m.model}</b> on {h}</span>
                <EyeChip fact={eyeOf(m.card)} testid="local-loaded-eye" />
                <span className="lc-vram-bar" aria-hidden="true"><span style={{ width: `${Math.min(100, pct ?? 0)}%` }} /></span>
                <span className="mono" data-testid="local-loaded-vram" title={`${gib(l.size_vram)} of ${gib(l.size)} on the GPU (/api/ps size_vram of size)`}>
                  {pct ?? "?"}% VRAM
                </span>
                {l.context_length ? <span className="mono muted" title="the window it is loaded at (/api/ps context_length)">window {l.context_length.toLocaleString("en-US")}</span> : null}
                <span className="muted" title="/api/ps expires_at">{until(l.expires)}</span>
                <span className="spacer" />
                <Button size="sm" variant="ghost" disabled={busy || !!why} onClick={() => void off(h, m.model)} data-testid="local-loaded-unload"
                        title={why || line("unload", h, m.model)}>Unload</Button>
              </li>
            );
          })}
        </ul>
      ) : (
        <p className="mono muted" data-testid="local-loaded-none">Nothing is loaded on these hosts right now.</p>
      )}
    </section>
  );
}
