// fleet-health: a doctor summary per harness (`GET fleet/health`): its
// status, the providers it is set up for and whether they answer, the Halo
// and Studio versions, free disk, how many sessions have their control
// socket open. Every harness is read at most once a minute (the route caches
// 60 s; a member answers the read-only `status` + `doctor` commands over the
// hub); the panel shows how old the reading is, and Refresh asks again now.
import { useEffect } from "react";
import { Button, Empty, Icon } from "../../lib/ui";
import type { MotionState } from "../../lib/motion";
import { Metric } from "../orchestra/bits";
import { loadHealth } from "./pload";
import { age, usePanels, type HealthRow } from "./pstore";
import { useNow } from "./store";

const STATUS: Record<string, string> = { ok: "all good", warn: "check it", bad: "needs you", unknown: "not read" };

function useHealth(): void {
  useEffect(() => {
    void loadHealth(false);
    const id = window.setInterval(() => !document.hidden && void loadHealth(false), 60_000);
    return () => window.clearInterval(id);
  }, []);
}

function Row({ h, now }: { h: HealthRow; now: number }) {
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

export function HealthDetail() {
  useHealth();
  const health = usePanels((s) => s.health);
  const error = usePanels((s) => s.healthError);
  const busy = usePanels((s) => s.healthBusy);
  const at = usePanels((s) => s.healthAt);
  const now = useNow(!!health, 5000);
  if (!health) return error ? <Empty title="Studio could not read the fleet's health" body={error} /> : <div className="og-wait mono muted">asking every harness...</div>;
  return (
    <div className="fhe" data-testid="fleet-health-detail">
      <div className="fhe-bar">
        <span className="mono muted" data-testid="fleet-health-age">cached {health.cache_s || 60} s · shown {at ? age(at / 1000, now) : "?"} ago</span>
        <span className="spacer" />
        <Button size="sm" icon={<Icon name="reset" />} disabled={busy} onClick={() => void loadHealth(true)} data-testid="fleet-health-refresh">
          {busy ? "Asking..." : "Refresh"}
        </Button>
      </div>
      <ul className="fhe-list">
        {health.harnesses.map((h) => <Row key={h.id} h={h} now={now} />)}
      </ul>
    </div>
  );
}

export function HealthGlance() {
  useHealth();
  const rows = usePanels((s) => s.health?.harnesses);
  const ok = (rows || []).filter((h) => h.status === "ok").length;
  const bad = (rows || []).filter((h) => h.status === "bad" || h.status === "warn");
  return (
    <div className="glance" data-testid="fleet-health-glance">
      <div className="glance-numbers">
        <Metric value={rows ? ok : "..."} label="healthy" tone={rows && ok === rows.length ? "ok" : undefined} />
        <Metric value={bad.length} label="to check" tone={bad.length ? "warn" : undefined} />
      </div>
      <div className="glance-hint mono">{bad.length ? bad.map((h) => h.name).join(" · ") : rows ? "every harness answers" : "asking every harness..."}</div>
    </div>
  );
}

export function useHealthMotion(): MotionState {
  const rows = usePanels((s) => s.health?.harnesses);
  if (!rows) return "none";
  if (rows.some((h) => h.status === "bad")) return "error";
  return rows.some((h) => h.status === "warn") ? "waiting" : "idle";
}
