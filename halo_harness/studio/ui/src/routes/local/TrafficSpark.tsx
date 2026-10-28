// The traffic view's sparkline per host (3.3.5.0 R1): the calls per minute of
// the last 15 minutes, a trim or a cut marked on its minute, and the bytes in
// and out of the newest minute that had any (the request bodies and the replies,
// the ledger's bytes_in / bytes_out). Each figure says what it counts as its title.
import type { Bucket } from "./types";
import { kb } from "./store";

const W = 220;
const H = 30;

export function TrafficSpark({ host, buckets }: { host: string; buckets: Bucket[] }) {
  const peak = Math.max(1, ...buckets.map((b) => b.calls));
  const t0 = buckets.length ? buckets[0].t : 0;
  const t1 = buckets.length ? buckets[buckets.length - 1].t : 0;
  const span = Math.max(60, t1 - t0);
  const x = (t: number) => ((t - t0) / span) * W;
  const y = (v: number) => H - 3 - (v / peak) * (H - 8);
  const pts = buckets.map((b) => `${x(b.t).toFixed(1)},${y(b.calls).toFixed(1)}`).join(" ");
  const calls = buckets.reduce((n, b) => n + b.calls, 0);
  const last = [...buckets].reverse().find((b) => b.bytes_in || b.bytes_out);
  return (
    <div className="lc-tspark" data-testid="local-traffic-spark" data-host={host} data-calls={calls}>
      <b className="mono">{host}</b>
      <svg viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="none" role="img" aria-label={`${host}: ${calls} calls in the window`}>
        <line className="lc-axis" x1={0} y1={H - 3} x2={W} y2={H - 3} />
        {buckets.length > 1 && <polyline className="lc-line" points={pts} fill="none" />}
        {buckets.map((b) =>
          b.trims || b.cuts ? (
            <circle key={b.t} className="lc-mark" data-testid="local-traffic-mark" data-kind={b.cuts ? "cut" : "trim"} cx={x(b.t)} cy={y(b.calls)} r={2.6}>
              <title>{new Date(b.t * 1000).toLocaleTimeString()}: {b.calls} calls, {b.trims} trimmed, {b.cuts} cut</title>
            </circle>
          ) : null,
        )}
      </svg>
      <span className="mono muted" title="calls to this host in the window (the ledger's lines)">{calls} calls</span>
      <span className="mono muted" data-testid="local-traffic-bytes"
            title="the newest minute with traffic: request bodies sent in, reply text and tool arguments out (bytes_in / bytes_out)">
        {last ? `in ${kb(last.bytes_in)}/min · out ${kb(last.bytes_out)}/min` : "no bytes yet"}
      </span>
    </div>
  );
}
