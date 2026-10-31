// One row of Local's traffic view (3.3.5.0 R1): a call to a local server as the
// ledger wrote it -- the time, the host, the model, who called from which
// machine, the kind (turn / compaction / small / repair / calibrate), the prompt
// tokens in and the reply tokens out, the window sent and where it came from,
// trimmed / cut / the status, tok/s, and the `fitted` and `switched from` marks
// -- or a steward event (loaded, unloaded, reloaded, spilled, trimmed ...) as a
// muted row between them. Every figure carries what it is as its title.
// 3.3.5.0 R4: a warming call says "warming" instead of a speed; "cache reused N %"; the preflight's decision.
import type { TRow } from "./types";
import { kb } from "./store";

const k = (n: number | null | undefined) => (typeof n !== "number" ? "?" : n >= 1000 ? `${(n / 1000).toFixed(1)}k` : String(n));

function clock(t: number | null): string {
  return t ? new Date(t * 1000).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" }) : "?";
}

export function EventRow({ r }: { r: TRow }) {
  return (
    <li className="lc-trow lc-tevent muted" data-testid="local-traffic-event" data-kind={r.kind} data-host={r.host} data-severity={r.severity}>
      <span className="mono lc-t">{clock(r.t)}</span>
      <span className="mono lc-th">{r.host}</span>
      <span className="og-chip mono" data-kind={r.kind}>{r.kind}</span>
      <span className="lc-tsay">{r.say}</span>
    </li>
  );
}

export function TrafficRow({ r }: { r: TRow }) {
  const bad = !r.ok;
  const state = bad ? String(r.status ?? "?") : r.cut ? "cut" : r.trimmed ? "trimmed" : "ok";
  return (
    <li className="lc-trow" data-testid="local-traffic-row" data-id={r.id} data-host={r.host} data-model={r.model || ""} data-kind={r.kind}
        data-from={r.from || "here"} data-state={state} data-trimmed={r.trimmed || undefined} data-cut={r.cut || undefined}
        data-fitted={r.fitted || undefined} title={r.error || undefined}>
      <span className="mono lc-t" title={r.at || ""}>{clock(r.t)}</span>
      <span className="mono lc-th">{r.host}</span>
      <span className="mono lc-tm" data-testid="local-traffic-model">{r.model}</span>
      <span className="mono muted lc-tf" title="the machine that made the call (the ledger's from)">{r.from || "this machine"}</span>
      <span className="og-chip mono" data-kind={r.kind}>{r.kind}</span>
      <span className="mono lc-tn" data-testid="local-traffic-in" title={`prompt tokens in (the server's count; Halo estimated ${k(r.estimate)})`}>
        in {k(r.prompt_in)}
      </span>
      <span className="mono lc-tn" data-testid="local-traffic-out" title="reply tokens out">out {k(r.reply_out)}</span>
      <span className="mono muted lc-tw" title={`the window sent, from ${r.window_source || "?"}`}>
        win {r.window ? k(r.window) : "default"}
      </span>
      <span className="mono lc-ts" data-state={state} data-testid="local-traffic-state">{state}</span>
      <span className="mono muted" title={r.warming ? "the first call after a load: never timed" : "the reply's eval rate"} data-testid="local-traffic-speed">
        {r.warming ? "warming" : typeof r.tok_s === "number" ? `${Math.round(r.tok_s)} tok/s` : ""}
      </span>
      {typeof r.cache_reused_pct === "number" && r.cache_reused_pct > 0 && (
        <span className="mono muted" data-testid="local-traffic-cache" title="the share of the prompt Ollama did not read again">cache reused {r.cache_reused_pct} %</span>
      )}
      {r.preflight && <span className="og-chip mono" data-testid="local-traffic-preflight" title="the preflight's decision before this call (the prompt was larger than the window)">preflight: {r.preflight}</span>}
      <span className="mono muted" title="the request body in, the reply out">{r.bytes_in ? `${kb(r.bytes_in)} / ${kb(r.bytes_out)}` : ""}</span>
      {r.fitted && <span className="og-chip mono" data-testid="local-traffic-fitted" title="a switch step fitted the session to this model before the call">fitted</span>}
      {r.switched_from && <span className="og-chip mono" title="the previous call of this session went to another model">from {r.switched_from}</span>}
    </li>
  );
}
