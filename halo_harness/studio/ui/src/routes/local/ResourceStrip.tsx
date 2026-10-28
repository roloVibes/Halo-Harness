// One host's live strip on Local -> Resources (3.3.5.0 R1): the VRAM bar with
// the name of what holds most of it, the GPU-use sparkline of the last 60 s,
// RAM, CPU (small) and the temperature when the tool reports one. Every number
// carries its source as its title (idea 2, "why" on every number): nvidia-smi,
// rocm-smi, ioreg, /proc/meminfo, GlobalMemoryStatusEx, /api/ps ... or why
// there is none. Samples come once a second (ollama_steward/resources.py); a
// host a fleet member serves says "via <member>" (idea 5, the hub as the one picture).
import type { Sample } from "./types";
import { gib } from "./store";

const W = 160;
const H = 28;

function pct(a: number | null, b: number | null): number | null {
  return typeof a === "number" && typeof b === "number" && b > 0 ? Math.round((100 * a) / b) : null;
}

function Spark({ samples, now }: { samples: Sample[]; now: number }) {
  const pts = samples.filter((s) => s.t >= now - 60 && typeof s.gpu === "number");
  const x = (t: number) => ((t - (now - 60)) / 60) * W;
  const y = (v: number) => H - 2 - (Math.max(0, Math.min(100, v)) / 100) * (H - 4);
  const line = pts.map((s) => `${x(s.t).toFixed(1)},${y(s.gpu as number).toFixed(1)}`).join(" ");
  return (
    <svg className="lc-spark" viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="none" data-testid="local-res-spark" data-points={pts.length}
         role="img" aria-label={`GPU use over the last minute: ${pts.length} samples`}>
      <line className="lc-axis" x1={0} y1={H - 2} x2={W} y2={H - 2} />
      {pts.length > 1 && <polyline className="lc-line" points={line} fill="none" />}
    </svg>
  );
}

function Num({ id, value, title, label }: { id: string; value: string; title: string; label: string }) {
  return (
    <span className="lc-num" data-testid={`local-res-${id}`} title={title}>
      <span className="lc-num-label mono">{label}</span> <span className="lc-num-value mono">{value}</span>
    </span>
  );
}

export function ResourceStrip({ host, samples }: { host: string; samples: Sample[] }) {
  const s = samples[samples.length - 1];
  if (!s) return null;
  const src = s.sources || {};
  const vp = pct(s.vram_used, s.vram_total);
  const rp = pct(s.ram_used, s.ram_total);
  const holders = (s.holders || []).map((h) => `${h.name || "?"} ${gib(h.bytes)} (${h.kind})`).join("\n");
  const age = Math.max(0, Math.round(Date.now() / 1000 - s.t));
  return (
    <section className="lc-strip" data-testid="local-resources-host" data-host={host} data-t={s.t} data-samples={samples.length}
             aria-label={`${host}: resources`}>
      <div className="lc-strip-head">
        <b className="mono">{host}</b>
        {s.from && <span className="og-chip mono" data-testid="local-res-from" title="samples this hub took from the fleet member that serves it">via {s.from}</span>}
        {s.unified && <span className="og-chip mono" title="the GPU shares the system memory">unified memory</span>}
        <span className="spacer" />
        <span className="mono muted" data-testid="local-res-age" title="the newest sample's age">{age <= 2 ? "live" : `${age}s ago`}</span>
      </div>
      <div className="lc-vram" title={`VRAM: ${src.vram || "?"}\nwho holds it: ${src.holder || "?"}${holders ? "\n" + holders : ""}`}>
        <span className="lc-vram-bar" aria-hidden="true"><span style={{ width: `${Math.min(100, vp ?? 0)}%` }} /></span>
        <span className="mono" data-testid="local-res-vram" data-used={s.vram_used ?? undefined} title={`VRAM: ${src.vram || "?"}`}>
          VRAM {gib(s.vram_used)} of {gib(s.vram_total)}{vp != null ? ` (${vp}%)` : ""}
        </span>
        <span className="mono lc-holder" data-testid="local-res-holder" title={`who holds it: ${src.holder || "?"}`}>{s.holder ? `held by ${s.holder}` : "nothing holds it"}</span>
      </div>
      <div className="lc-strip-nums">
        <span className="lc-gpu" title={`GPU use: ${src.gpu || "?"}`}>
          <Num id="gpu" label="GPU" value={typeof s.gpu === "number" ? `${s.gpu}%` : "n/a"} title={`GPU use: ${src.gpu || "?"}`} />
          <Spark samples={samples} now={s.t} />
        </span>
        <Num id="ram" label="RAM" value={`${gib(s.ram_used)} of ${gib(s.ram_total)}${rp != null ? ` (${rp}%)` : ""}`} title={`RAM: ${src.ram || "?"}`} />
        <Num id="cpu" label="CPU" value={typeof s.cpu === "number" ? `${Math.round(s.cpu)}%` : "?"} title={`CPU: ${src.cpu || "?"}`} />
        <Num id="temp" label="temp" value={typeof s.temp === "number" ? `${Math.round(s.temp)} °C` : "n/a"} title={`temperature: ${src.temp || "?"}`} />
        {typeof s.others === "number" && s.others > 0 && (
          <Num id="others" label="not Ollama" value={gib(s.others)} title={`${src.others || ""}: the fit planner counts it as held`} />
        )}
      </div>
    </section>
  );
}
