// fleet-health: a doctor summary per harness (`GET fleet/health`): its
// status, the providers it is set up for and whether they answer, the Halo
// and Studio versions, free disk, how many sessions have their control
// socket open. Every harness is read at most once a minute (the route caches
// 60 s; a member answers the read-only `status` + `doctor` commands over the
// hub); the panel shows how old the reading is, and Refresh asks again now.
import { useEffect } from "react";
import { loadHealth } from "./pload";
import { age, type HealthRow } from "./pstore";

const STATUS: Record<string, string> = { ok: "all good", warn: "check it", bad: "needs you", unknown: "not read" };

export function useHealth(): void {
  useEffect(() => {
    void loadHealth(false);
    const id = window.setInterval(() => !document.hidden && void loadHealth(false), 60_000);
    return () => window.clearInterval(id);
  }, []);
}

export function HealthRowView({ h, now }: { h: HealthRow; now: number }) {
  const providers = h.providers || [];
  const up = providers.filter((p) => p.reachable).length;
  return (
    <li className="fhe-row" data-testid="fleet-health-row" data-status={h.status} data-id={h.id}>
      <div className="fhe-top">
        <span className="fhe-dot" data-status={h.status} aria-hidden="true" />
        <b>{h.name}</b>
        <span className="og-chip mono" data-status={h.status}>{STATUS[h.status] || h.status}</span>
        <span className="spacer" />
        <span className="mono muted" title="when this harness was read">{h.checked ? `read ${age(h.checked, now)} ago${h.cached ? " (cached)" : ""}` : "not read"}</span>
      </div>
      <dl className="fhe-facts mono">
        <dt>providers</dt>
        <dd>{providers.length ? `${up} of ${providers.length} answer · ` + providers.map((p) => `${p.name}${p.reachable === false ? " (down)" : p.reachable ? "" : " (?)"}`).join(", ") : "none set up"}</dd>
        <dt>versions</dt>
        <dd>halo {h.version || "?"} · studio {h.studio?.version || "?"}{h.studio?.running ? " (running)" : ""}{h.python ? ` · python ${h.python}` : ""}</dd>
        <dt>disk</dt>
        <dd>{h.disk ? `${h.disk.free_gb.toFixed(0)} GB free of ${h.disk.total_gb.toFixed(0)} (${h.disk.free_pct.toFixed(0)}%)` : "?"}</dd>
        <dt>sockets</dt>
        <dd>{h.sockets ?? "?"} session{h.sockets === 1 ? "" : "s"} with a control socket</dd>
      </dl>
      {h.note && <p className="fhe-note muted">{h.note}</p>}
    </li>
  );
}
