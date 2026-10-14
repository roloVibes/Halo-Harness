// Media status: the reachable dot (ticks green on each check), the ComfyUI
// version, the GPU's VRAM bar, the inventory cache's age and Scan. When the
// server does not answer, the panel is one card that says how to fix it.
import { useStateMotion, type MotionState } from "../../lib/motion";
import { Button } from "../../lib/ui";
import { Metric } from "../orchestra/bits";
import { ago, gib, loadStatus, scan, useMedia } from "./store";

function Dot() {
  const st = useMedia((s) => s.status);
  const at = useMedia((s) => s.statusAt);
  const motion = useStateMotion(st?.reachable ? "live" : "none", at);
  const status = st?.reachable ? "open" : st?.reachable === false ? "down" : "connecting";
  return <span className="feed-dot md-dot" data-status={status} {...motion} aria-hidden="true" />;
}

function Vram() {
  const gpu = useMedia((s) => s.status?.gpus?.[0]);
  if (!gpu?.vram_total) return <div className="md-vram muted mono">no GPU reported</div>;
  const used = Math.max(0, gpu.vram_total - (gpu.vram_free || 0));
  const pct = Math.round((used / gpu.vram_total) * 100);
  return (
    <div className="md-vram" title={`${gpu.name}: ${gib(used)} of ${gib(gpu.vram_total)} in use`}>
      <div className="md-vram-head mono">
        <span>{gpu.name.replace(/^cuda:\d+\s*/, "")}</span>
        <span>{gib(used)} / {gib(gpu.vram_total)}</span>
      </div>
      <div className="md-bar" role="meter" aria-valuenow={pct} aria-valuemin={0} aria-valuemax={100} aria-label="VRAM in use">
        <span className="md-bar-fill" data-tone={pct > 85 ? "warn" : "accent"} style={{ width: `${pct}%` }} />
      </div>
    </div>
  );
}

function ScanButton() {
  const scanning = useMedia((s) => s.scanning);
  return (
    <Button size="sm" onClick={() => void scan()} disabled={scanning} title="Read the server's model folders and saved workflows into the cache">
      {scanning ? "Scanning..." : "Scan"}
    </Button>
  );
}

/** ComfyUI does not answer: what to do, in order. */
export function FixCard() {
  const st = useMedia((s) => s.status);
  return (
    <div className="md-fix" data-motion="error" data-testid="media-fix">
      <div className="glance-row">
        <Dot />
        <span className="glance-kicker mono md-state">COMFYUI DOES NOT ANSWER</span>
      </div>
      <p>
        Studio looked for it at <span className="mono">{st?.url || "the configured address"}</span>
        {st?.error ? ` (${st.error})` : ""}.
      </p>
      <ol className="md-fix-steps">
        <li>Start ComfyUI on its machine (it listens on port 8188).</li>
        <li>
          Point Halo at it: <code>halo media init --url &lt;its address&gt;</code>, or set COMFY_URL.
        </li>
        <li>Press Check again: the dot turns green when it answers.</li>
      </ol>
      <Button size="sm" variant="primary" onClick={() => void loadStatus()}>
        Check again
      </Button>
    </div>
  );
}

export function StatusGlance() {
  const st = useMedia((s) => s.status);
  if (!st) return <div className="og-wait mono muted">Asking ComfyUI how it is...</div>;
  if (st.reachable === false) return <FixCard />;
  return (
    <div className="glance md-status">
      <div className="glance-row">
        <Dot />
        <span className="glance-kicker mono">COMFYUI</span>
        <span className="md-state mono" data-ok={String(!!st.reachable)}>{st.reachable ? "ONLINE" : "CHECKING"}</span>
        <span className="spacer" />
        <ScanButton />
      </div>
      <div className="glance-numbers">
        <Metric value={st.version || "-"} label="version" />
        <Metric value={st.cache?.rows ?? 0} label={`models · scanned ${ago(st.cache?.age_s)}`} />
      </div>
      <Vram />
    </div>
  );
}

export function StatusDetail() {
  const st = useMedia((s) => s.status);
  if (!st || st.reachable === false) return <StatusGlance />;
  return (
    <div className="md-detail">
      <StatusGlance />
      <dl className="og-facts mono">
        <dt>server</dt>
        <dd>{st.url || "-"}</dd>
        <dt>checked</dt>
        <dd>{ago(st.age_s)}{st.checking ? " (checking)" : ""}</dd>
        <dt>cache</dt>
        <dd>{st.cache?.rows ?? 0} models, {st.cache?.workflows ?? 0} saved workflows, scanned {ago(st.cache?.age_s)}</dd>
        <dt>mcp</dt>
        <dd>{st.registered ? `${st.registered.command || ""} ${(st.registered.args || []).join(" ")}` : "not registered: halo media init adds it"}</dd>
      </dl>
      {(st.gpus || []).slice(1).map((g) => (
        <div key={g.name} className="mono muted">{g.name}: {gib(g.vram_free)} free of {gib(g.vram_total)}</div>
      ))}
    </div>
  );
}

export function StatusSettings() {
  return (
    <div className="og-settings">
      <Button size="sm" onClick={() => void loadStatus()}>Check now</Button>
      <ScanButton />
      <p className="muted">Studio checks the server every 15 s while a Media panel is open. The address is COMFY_URL or the config's comfy.url.</p>
    </div>
  );
}

export function useStatusMotion(): MotionState {
  const st = useMedia((s) => s.status);
  const scanning = useMedia((s) => s.scanning);
  if (scanning || st?.checking) return "working";
  return st?.reachable ? "idle" : st?.reachable === false ? "error" : "none";
}
