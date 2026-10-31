// 3.3.7.0 R3 (G12): Local -> Hosts' Place block -- where each local lane of the active lineup should run. Place asks
// every reachable host (a paired halo host's route answer, else this machine's own reads; GET local/place,
// local_sched/place.py) and lists one row per lane: its host and why (fits, warm, the load seconds, what it
// evicts). Apply writes host_for on each moved lane's <host>|<model>|<role> profile (POST local/place): Halo-side
// only, nothing pulls and nothing loads until a lane asks.
import { useState } from "react";
import { api } from "../../lib/api";
import { Button } from "../../lib/ui";

type Row = { lane: string; model: string; host: string | null; from_host: string | null; moved: boolean; why: string };
type Plan = { lineup: string; line: string; rows: Row[]; local: boolean };

const text = (e: unknown) => (e instanceof Error ? e.message : String(e));

export function HostsPlace() {
  const [plan, setPlan] = useState<Plan | null>(null);
  const [said, setSaid] = useState<{ ok: boolean; text: string } | null>(null);
  const [busy, setBusy] = useState(false);
  const place = async () => {
    setBusy(true);
    try {
      setPlan(await api.get<Plan>("local/place"));
      setSaid(null);
    } catch (e) {
      setSaid({ ok: false, text: text(e) });
    } finally {
      setBusy(false);
    }
  };
  const apply = async () => {
    setBusy(true);
    try {
      const r = await api.post<{ written: string[] }>("local/place", { lineup: plan?.lineup || "" });
      setSaid({ ok: true, text: (r.written || []).join(" · ") });
    } catch (e) {
      setSaid({ ok: false, text: text(e) });
    } finally {
      setBusy(false);
    }
  };
  const moved = !!plan?.rows.some((r) => r.moved);
  return (
    <section className="lc-block" aria-label="PLACE" data-testid="local-place">
      <div className="rail-label mono">PLACE · WHERE EACH LANE OF THE LINEUP RUNS</div>
      <div className="lc-model-acts">
        <Button size="sm" disabled={busy} onClick={() => void place()} data-testid="local-place-run"
                title="halo local place: every reachable host asked (a halo host's route, else the local reads); nothing loads">Place</Button>
        {moved && (
          <Button size="sm" variant="primary" disabled={busy} onClick={() => void apply()} data-testid="local-place-apply"
                  title="halo local place --apply: host_for on each moved lane's profile (Halo-side only)">Apply</Button>
        )}
        {plan && <span className="mono muted" data-testid="local-place-lineup">lineup {plan.lineup || "none in force"}</span>}
      </div>
      {plan && !plan.local && <p className="muted" data-testid="local-place-none">This lineup has no local lanes (no ol: models).</p>}
      {plan && plan.local && (
        <ul className="lc-loaded">
          {plan.rows.map((r) => (
            <li key={r.lane} data-testid="local-place-row" data-lane={r.lane} data-host={r.host || ""} data-moved={r.moved || undefined}>
              <span className="mono">{r.lane}: {r.model} on {r.host || "nowhere"}</span>
              <span className="muted">{r.why}{r.moved ? ` (from ${r.from_host})` : ""}</span>
            </li>
          ))}
        </ul>
      )}
      {said && <div className="mono lc-said" data-ok={said.ok || undefined} data-testid="local-place-said">{said.text}</div>}
    </section>
  );
}
