// fleet-costs: what the fleet spends today (`GET fleet/costs`; today = the
// sessions started today, local day): a ticker for the whole fleet, then per
// harness, per project and per session; the spend caps (`fleet.caps.*`,
// `POST fleet/caps`): a cap reached pauses the sessions in its scope and
// raises an attention row, Lift for today resumes them; the provider
// balances the balances workers last read, when there are any.
import { useEffect, useState } from "react";
import { Button, Empty, Icon } from "../../lib/ui";
import type { MotionState } from "../../lib/motion";
import { Metric } from "../orchestra/bits";
import { cost, short } from "../orchestra/format";
import { answerRow, saveCaps, showFleetPanel } from "./extras";
import { useTicker } from "./MapNode";
import { loadCosts } from "./pload";
import { usePanels, type CapKey, type Costs } from "./pstore";

const REFRESH_MS = 10_000;
const CAP_LABEL: Record<CapKey, string> = { per_harness_usd_per_day: "per harness, per day", per_project_usd_per_day: "per project, per day", fleet_usd_per_day: "the whole fleet, per day" };

function useCosts(): void {
  useEffect(() => {
    void loadCosts();
    const id = window.setInterval(() => !document.hidden && void loadCosts(), REFRESH_MS);
    return () => window.clearInterval(id);
  }, []);
}

function Ticker({ usd }: { usd: number }) {
  const shown = useTicker(usd);
  return <span className="fco-ticker mono" data-testid="fleet-cost-ticker">{cost(shown)}</span>;
}

function Caps({ c }: { c: Costs }) {
  const [draft, setDraft] = useState<Record<string, string>>({});
  const keys = (c.keys?.length ? c.keys : (Object.keys(CAP_LABEL) as CapKey[])) as CapKey[];
  const value = (k: CapKey) => (k in draft ? draft[k] : c.caps?.[k] == null ? "" : String(c.caps[k]));
  const dirty = Object.keys(draft).length > 0;
  const save = async () => {
    const out: Partial<Record<CapKey, number | null>> = {};
    for (const k of keys) if (k in draft) out[k] = draft[k].trim() === "" ? null : Number(draft[k]);
    if (await saveCaps(out)) setDraft({});
  };
  return (
    <section className="fco-caps" data-testid="fleet-caps">
      <div className="rail-label mono">SPEND CAPS · EMPTY = NO CAP</div>
      {keys.map((k) => (
        <label key={k} className="fco-cap">
          <span>{CAP_LABEL[k] || k}</span>
          <span className="fco-usd mono">$</span>
          <input className="input mono" inputMode="decimal" value={value(k)} placeholder="no cap" data-testid={`fleet-cap-${k}`}
                 onChange={(e) => setDraft((d) => ({ ...d, [k]: e.target.value }))} onKeyDown={(e) => e.key === "Enter" && void save()} />
        </label>
      ))}
      <div className="fco-cap-actions">
        <Button size="sm" variant="primary" disabled={!dirty} onClick={() => void save()} data-testid="fleet-caps-save">Save caps</Button>
        {dirty && <Button size="sm" variant="ghost" onClick={() => setDraft({})}>Undo</Button>}
      </div>
    </section>
  );
}

function Reached({ c }: { c: Costs }) {
  const rows = usePanels((s) => s.attention.filter((r) => r.kind === "cap"));
  if (!c.reached?.length) return null;
  return (
    <section className="fco-reached" data-testid="fleet-cap-reached">
      {c.reached.map((r) => {
        const row = rows.find((x) => x.target?.scope === r.scope && x.target?.key === r.key);
        return (
          <div key={r.scope + r.key} className="fco-hit" data-lifted={r.lifted || undefined}>
            <Icon name="diamond" />
            <span><b>{r.label || r.key}</b> reached its cap: {cost(r.spent)} of {cost(r.cap)}{r.lifted ? " · lifted for today" : ` · ${r.sessions.length} session${r.sessions.length === 1 ? "" : "s"} paused`}</span>
            <span className="spacer" />
            {row && <Button size="sm" onClick={() => void answerRow(row, "a")}>{row.keys.a || "Lift"}</Button>}
            {!row && !r.lifted && <Button size="sm" variant="ghost" onClick={() => showFleetPanel("fleet-attention")}>Attention</Button>}
          </div>
        );
      })}
    </section>
  );
}

function balanceLines(b: Record<string, unknown>): string[] {
  const out: string[] = [];
  for (const [name, raw] of Object.entries(b || {})) {
    const e = raw as { amount?: number; kind?: string; status?: string } | null;
    if (!e || typeof e.amount !== "number") continue;
    out.push(`${name}: $${e.amount.toFixed(2)} ${e.kind === "spend" ? "spent" : "left"}`);
  }
  return out;
}

export function CostsDetail() {
  useCosts();
  const c = usePanels((s) => s.costs);
  const error = usePanels((s) => s.costsError);
  if (!c) return error ? <Empty title="Studio could not read the costs" body={error} /> : <div className="og-wait mono muted">reading today's spend...</div>;
  const balances = balanceLines(c.balances);
  return (
    <div className="fco" data-testid="fleet-costs-detail">
      <div className="fco-top">
        <div>
          <div className="rail-label mono">THE FLEET TODAY</div>
          <Ticker usd={c.fleet} />
        </div>
        {balances.length > 0 && <div className="fco-bal mono muted">{balances.map((l) => <div key={l}>{l}</div>)}</div>}
      </div>
      <Reached c={c} />
      <div className="fco-grid">
        <section>
          <div className="rail-label mono">PER HARNESS</div>
          {c.harnesses.map((h) => (
            <div key={h.id} className="fco-row" data-testid="fleet-cost-harness"><span>{h.name}{h.local ? " (here)" : ""}</span><span className="mono muted">{h.sessions} s</span><b className="mono">{cost(h.usd)}</b></div>
          ))}
        </section>
        <section>
          <div className="rail-label mono">PER PROJECT</div>
          {c.projects.map((p) => (
            <div key={p.key} className="fco-row" title={p.harnesses.join(", ")}><span>{short(p.label, 24)}</span><span className="mono muted">{p.harnesses.length} h</span><b className="mono">{cost(p.usd)}</b></div>
          ))}
          {!c.projects.length && <p className="muted">No project spent anything today.</p>}
        </section>
      </div>
      <section className="fco-sessions">
        <div className="rail-label mono">PER SESSION (THIS SESSION AND TODAY)</div>
        {c.sessions.map((s) => (
          <div key={s.harness + s.session_id} className="fco-row"><span>{short(s.title, 36)}</span><span className="mono muted">{s.harness_name}{s.today ? "" : " · earlier"}</span><b className="mono">{cost(s.usd)}</b></div>
        ))}
      </section>
      <Caps c={c} />
    </div>
  );
}

export function CostsGlance() {
  useCosts();
  const c = usePanels((s) => s.costs);
  const top = c ? [...c.harnesses].sort((a, b) => b.usd - a.usd)[0] : null;
  return (
    <div className="glance" data-testid="fleet-costs-glance">
      <div className="glance-numbers">
        <Metric value={c ? <Ticker usd={c.fleet} /> : "..."} label="fleet today" tone="accent" />
        <Metric value={c?.reached?.filter((r) => !r.lifted).length || 0} label="caps reached" tone={c?.reached?.some((r) => !r.lifted) ? "warn" : undefined} />
      </div>
      <div className="glance-hint mono">{top ? `most: ${top.name} ${cost(top.usd)}` : "Expand for each harness, project, session and the caps."}</div>
    </div>
  );
}

export function useCostsMotion(): MotionState {
  const hit = usePanels((s) => !!s.costs?.reached?.some((r) => !r.lifted));
  return hit ? "waiting" : "idle";
}
