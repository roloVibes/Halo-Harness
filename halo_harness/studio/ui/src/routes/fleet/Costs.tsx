// fleet-costs: what the fleet spends today (`GET fleet/costs`; today = the
// sessions started today, local day): a ticker for the whole fleet, then per
// harness, per project and per session; the spend caps (`fleet.caps.*`,
// `POST fleet/caps`): a cap reached pauses the sessions in its scope and
// raises an attention row, Lift for today resumes them; the provider
// balances the balances workers last read, when there are any.
import { useEffect, useMemo, useState } from "react";
import { Button, Icon } from "../../lib/ui";
import { cost } from "../orchestra/format";
import { answerRow, saveCaps, showFleetPanel } from "./extras";
import { useTicker } from "../agents/live/nodeBits";
import { loadCosts } from "./pload";
import { usePanels, type CapKey, type Costs } from "./pstore";

const REFRESH_MS = 10_000;
const CAP_LABEL: Record<CapKey, string> = { per_harness_usd_per_day: "per harness, per day", per_project_usd_per_day: "per project, per day", fleet_usd_per_day: "the whole fleet, per day" };

export function useCosts(): void {
  useEffect(() => {
    void loadCosts();
    const id = window.setInterval(() => !document.hidden && void loadCosts(), REFRESH_MS);
    return () => window.clearInterval(id);
  }, []);
}

export function Ticker({ usd }: { usd: number }) {
  const shown = useTicker(usd);
  return <span className="fco-ticker mono" data-testid="fleet-cost-ticker">{cost(shown)}</span>;
}

export function Caps({ c }: { c: Costs }) {
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

export function Reached({ c }: { c: Costs }) {
  // 3.1.4.0 R1: select the list itself (a filtered copy is a new value on every read: React re-renders forever)
  const attention = usePanels((s) => s.attention);
  const rows = useMemo(() => attention.filter((r) => r.kind === "cap"), [attention]);
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

export function balanceLines(b: Record<string, unknown>): string[] {
  const out: string[] = [];
  for (const [name, raw] of Object.entries(b || {})) {
    const e = raw as { amount?: number; kind?: string; status?: string } | null;
    if (!e || typeof e.amount !== "number") continue;
    out.push(`${name}: $${e.amount.toFixed(2)} ${e.kind === "spend" ? "spent" : "left"}`);
  }
  return out;
}
