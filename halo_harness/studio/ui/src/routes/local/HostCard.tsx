// One host on Local -> Hosts (3.3.5.0 R1): its URL, kind, version and who serves
// it; what is loaded now (the model, its VRAM share, when it unloads) with
// Unload; every installed model with Load (a warm generate at the profile's
// window) and the fit meter (idea 1); keep-alive for the next Load; the hardware
// card's lines, the profiles, who calls it (the ledger's `from`, 24 h), the
// steward's last finding; "Make it fit" (idea 4: the fit planner's chosen option
// applied through steward/apply, Undo beside it). A discovered server has "Add to
// hosts" (Setup's own writer). A control that cannot run from here is disabled
// with the reason as its title and under it. Nothing here writes a server's settings. 3.3.5.0 R5: a server Halo started
// (Local -> Hugging Face) is a card of its own with its port, model, flags, Stop and Log; a local server Halo did not
// start has Stop disabled, its title saying where it is stopped.
import { useState } from "react";
import { Button, FitMeter } from "../../lib/ui";
import type { Fit } from "../../lib/ui/FitMeter";
import { openLog, stopServer, useHf } from "./hfstore";
import { addHost, gib, loadModel, makeItFit, undoFit, unloadModel, useLocal } from "./store";
import type { HostCard as Host } from "./types";

const KEEPS = ["", "5m", "30m", "1h", "-1"];

function until(iso: string | null): string {
  if (!iso) return "";
  const s = Math.round((Date.parse(iso) - Date.now()) / 1000);
  return !Number.isFinite(s) ? "" : s <= 0 ? "unloading" : s < 120 ? `unloads in ${s}s` : `unloads in ${Math.round(s / 60)}m`;
}

function Said({ k }: { k: string }) {
  const s = useLocal((st) => st.said[k]);
  return s ? <div className="mono lc-said" data-ok={s.ok || undefined} data-testid="local-said">{s.text}</div> : null;
}

function Fitting({ h }: { h: Host }) {
  const s = useLocal((st) => st.said[`fit|${h.name}`]);
  const busy = useLocal((st) => !!st.busy);
  const c = h.plan?.chosen;
  if (!h.plan) return null;
  return (
    <div className="lc-fit" data-testid="local-host-fit">
      <span className="lc-fit-says" data-fits={h.plan.fits_now ? "yes" : "no"}>{h.plan.says}</span>
      {c && c.changes.length > 0 && !s?.undo && (
        <Button size="sm" variant="primary" disabled={busy || !c.fits} onClick={() => void makeItFit(h)} data-testid="local-make-fit"
                title={`${c.says}; you lose: ${c.lose}`}>
          Make it fit
        </Button>
      )}
      {s?.undo ? (
        <Button size="sm" variant="ghost" disabled={busy} onClick={() => void undoFit(h, s.undo || 0)} data-testid="local-fit-undo">Undo</Button>
      ) : null}
      <Said k={`fit|${h.name}`} />
    </div>
  );
}

function Managed({ h }: { h: Host }) {
  const m = h.managed;
  const busy = useHf((s) => s.busy);
  const said = useHf((s) => s.said[`host|${h.name}`]);
  if (h.source === "local server") {
    return (
      <div className="lc-model-acts">
        <Button size="sm" disabled data-testid="local-host-stop" title={h.controls.why}>Stop</Button>
      </div>
    );
  }
  if (!m) return null;
  const f = m.flags || ({} as NonNullable<Host["managed"]>["flags"]);
  return (
    <div className="lc-managed" data-testid="local-host-managed" data-alive={m.alive ? "yes" : "no"} data-ready={m.ready ? "yes" : "no"}>
      <div className="mono" data-testid="local-host-managed-model" title={m.model_path}>{m.model} · port {m.port} · pid {m.pid ?? "?"}{m.keep ? " · keep" : ""}</div>
      <div className="mono muted" data-testid="local-host-flags">
        <span title={m.sources?.window || ""}>-c {f.window?.toLocaleString("en-US")}</span>{" "}
        <span title={m.sources?.ngl || ""}>-ngl {f.ngl}</span>{" "}
        <span title={m.sources?.parallel || ""}>-np {f.parallel}</span>
        {f.kv_type ? <span title={m.sources?.kv_type || ""}> --cache-type-k/v {f.kv_type}</span> : null}
        {" · "}{m.alive ? (m.ready ? "ready" : "loading") : "gone"}
      </div>
      <div className="lc-model-acts">
        <Button size="sm" disabled={busy} onClick={() => void stopServer(m.id, `host|${h.name}`)} data-testid="local-host-stop"
                title={`${m.stop_cli} (terminate, then kill after 10 s)`}>Stop</Button>
        <Button size="sm" onClick={() => void openLog(m.id)} data-testid="local-host-log" title={m.log_cli}>Log</Button>
        {said && <span className="mono lc-said" data-ok={said.ok || undefined} data-testid="local-host-stop-said">{said.text}</span>}
      </div>
    </div>
  );
}

export function HostCard({ h, fits }: { h: Host; fits: Record<string, Fit> }) {
  const busy = useLocal((s) => s.busy);
  const [keep, setKeep] = useState("");
  const [name, setName] = useState(h.name);
  const ctl = h.controls;
  const loaded = new Set(h.loaded.map((m) => m.model || ""));
  const card = h.card_lines.filter((l) => /^(GPU |memory: |server |other: )/.test(l));
  return (
    <article className="lc-host" data-testid="local-host-card" data-name={h.name} data-source={h.source} data-kind={h.kind}
             data-control={ctl.ok ? "yes" : "no"}>
      <header className="lc-host-head">
        <b className="mono">{h.name}</b>
        <span className="og-chip mono" data-testid="local-host-kind">{h.kind}</span>
        <span className="og-chip mono" data-testid="local-host-source">{h.source}</span>
        {h.version && <span className="mono muted" title="the server's version (/api/version)">v{h.version}</span>}
        <span className="spacer" />
        <span className="mono muted" data-testid="local-host-served">{h.served_here ? "served here" : h.served_by ? `served by ${h.served_by}` : ""}</span>
      </header>
      <div className="mono lc-host-url" data-testid="local-host-url">{h.url}</div>
      <Managed h={h} />
      {card.length > 0 && <div className="mono muted lc-host-card" title={h.card_lines.join("\n")}>{card.map((l) => <div key={l}>{l}</div>)}</div>}
      {h.loaded.length > 0 && <div className="rail-label mono" data-testid="local-host-loaded-label">LOADED NOW</div>}
      {h.loaded.length > 0 && (
        <ul className="lc-loaded">
          {h.loaded.map((m) => (
            <li key={m.model} data-testid="local-host-loaded" data-model={m.model || ""}>
              <span className="mono">{m.model}</span>
              <span className="lc-vram-bar" aria-hidden="true"><span style={{ width: `${Math.min(100, m.vram_pct ?? 0)}%` }} /></span>
              <span className="mono" data-testid="local-host-vram" title={`${gib(m.size_vram)} of ${gib(m.size)} on the GPU`}>
                {m.vram_pct ?? "?"}% VRAM
              </span>
              <span className="muted">{until(m.expires)}</span>
              <span className="spacer" />
              <Button size="sm" variant="ghost" disabled={!!busy || !ctl.ok} title={ctl.ok ? `halo models unload ${m.model} --host ${h.name} (keep_alive 0, via ${ctl.via})` : ctl.why}
                      onClick={() => void unloadModel(h.name, m.model || "")} data-testid="local-unload">Unload</Button>
            </li>
          ))}
        </ul>
      )}
      {h.models.length > 0 && !h.managed && (
        <ul className="lc-installed">
          {h.models.filter((m) => !loaded.has(m)).map((m) => (
            <li key={m} data-testid="local-host-model" data-model={m}>
              <span className="mono">{m}</span>
              <FitMeter fit={fits[m]} />
              <span className="spacer" />
              <Button size="sm" disabled={!!busy || !ctl.ok} title={ctl.ok ? `halo models load ${m} --host ${h.name} (a warm generate at the profile's window, via ${ctl.via})` : ctl.why}
                      onClick={() => void loadModel(h.name, m, keep)} data-testid="local-load">Load</Button>
              <Said k={`${h.name}|${m}`} />
            </li>
          ))}
          <li className="lc-keep">
            <label className="mono muted">keep-alive for Load{" "}
              <select value={keep} onChange={(e) => setKeep(e.target.value)} data-testid="local-keep" disabled={!ctl.ok}>
                {KEEPS.map((v) => <option key={v} value={v}>{v === "" ? "the profile's" : v === "-1" ? "until unloaded" : v}</option>)}
              </select>
            </label>
          </li>
        </ul>
      )}
      {h.loaded.map((m) => <Said key={m.model} k={`${h.name}|${m.model}`} />)}
      {Object.keys(h.profiles).length > 0 && (
        <div className="mono muted lc-host-line" data-testid="local-host-profiles">
          profiles: {Object.entries(h.profiles).map(([m, p]) => `${m} ${[p.num_ctx ? `window ${p.num_ctx.toLocaleString("en-US")}` : "", p.num_predict ? `reserve ${p.num_predict}` : "", p.keep_alive != null ? `keep-alive ${p.keep_alive}` : ""].filter(Boolean).join(" ")} (by ${p.by || "you"})`).join(" · ")}
        </div>
      )}
      <div className="mono muted lc-host-line" data-testid="local-host-users" title="the ledger's from over the last 24 hours">
        who calls it: {h.users.length ? h.users.map((u) => `${u.from || "this machine"} ${u.calls}`).join(" · ") : "nobody in the last 24 h"}
      </div>
      {h.finding && <div className="lc-host-line" data-testid="local-host-finding">steward: {h.finding}</div>}
      <Fitting h={h} />
      {h.source === "discovered" && (
        <div className="lc-add">
          <input className="input mono" value={name} onChange={(e) => setName(e.target.value)} aria-label="host name" data-testid="local-add-name" />
          <Button size="sm" variant="primary" disabled={!!busy} onClick={() => void addHost(h.url, name)} data-testid="local-add">Add to hosts</Button>
          <Said k={`add|${h.url}`} />
        </div>
      )}
      {!ctl.ok && h.source !== "discovered" && ctl.why && <p className="muted lc-why" data-testid="local-control-why">{ctl.why}</p>}
    </article>
  );
}
