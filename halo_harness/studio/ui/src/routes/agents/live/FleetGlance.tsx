// Agents -> Live's inspector with nothing picked (3.3.16.0 R2 "the Fleet fold"): the fleet at a glance, summary first
// -- "while you were away" when it applies (Digest.tsx's card as a block, never a pop-up), then one line each: the
// machines (live / idle / away), the agents working, the decisions waiting on you (amber; a click opens Attention), what
// the fleet spent today against its cap; the caps reached (Lift); one row per machine (a click puts it in the
// inspector). The Fleet section's People, Costs and Tree panels drew these before.
import { useMemo, type ReactNode } from "react";
import { Button } from "../../../lib/ui";
import { cost, costToday } from "../../orchestra/format";
import { balanceLines, Reached, Ticker, useCosts } from "../../fleet/Costs";
import { DigestCard } from "../../fleet/Digest";
import { presence } from "../../fleet/People";
import { useAttnCount, usePanels } from "../../fleet/pstore";
import { useCounts, useFleet, useNow } from "../../fleet/store";
import { toggleAttention } from "../attention";
import { pickLive } from "./scope";

function Line({ k, children, tone, testid }: { k: string; children: ReactNode; tone?: "warn"; testid?: string }) {
  return (
    <div data-line={k} data-tone={tone} data-testid={testid}>
      <dt className="mono">{k}</dt>
      <dd>{children}</dd>
    </div>
  );
}

export function FleetGlance() {
  useCosts();
  const harnesses = useFleet((s) => s.harnesses);
  const c = useCounts();
  const waiting = useAttnCount(c.attention);
  const costs = usePanels((s) => s.costs);
  const now = useNow(true, 10_000);
  const by = useMemo(() => {
    const out = { live: 0, idle: 0, away: 0 };
    for (const h of harnesses) out[presence(h, now)] += 1;
    return out;
  }, [harnesses, now]);
  const cap = costs?.caps?.fleet_usd_per_day;
  return (
    <div className="ri-sum lv-glance" data-testid="live-glance">
      <DigestCard where="live" />
      <dl className="ri-summary" data-testid="live-glance-lines">
        <Line k="machines" testid="live-glance-machines">{harnesses.length} · {by.live} live · {by.idle} idle · {by.away} away</Line>
        <Line k="working">{c.live} agent{c.live === 1 ? "" : "s"} of {c.agents} in {c.sessions} session{c.sessions === 1 ? "" : "s"}</Line>
        <Line k="waits on you" tone={waiting ? "warn" : undefined} testid="live-glance-waiting">
          {waiting ? <button className="og-link mono" onClick={toggleAttention}>{waiting} decision{waiting === 1 ? "" : "s"} (Attention, A)</button> : "nothing"}
        </Line>
        <Line k="spent today" testid="live-glance-spend">
          {costs ? <><Ticker usd={costs.fleet} />{cap ? ` of ${cost(cap)} cap` : " · no fleet cap"}</> : "reading today's spend..."}
        </Line>
      </dl>
      {costs && balanceLines(costs.balances).length > 0 && <div className="fco-bal mono muted" data-testid="live-glance-balances">{balanceLines(costs.balances).join(" · ")}</div>}
      {costs && <Reached c={costs} />}
      <ul className="ri-rows" aria-label="The machines">
        {harnesses.map((h) => (
          <li key={h.id} className="ri-row" data-density="row" data-testid="live-glance-machine" data-harness={h.id}>
            <button className="ri-row-main" onClick={() => pickLive("machine", h.id)} title="Its summary: who, what it shares, its health, specs and spend">
              <span className="ri-row-title"><span className="fpe-dot" data-presence={presence(h, now)} aria-hidden="true" /> {h.name || h.id.slice(0, 8)}</span>
              <span className="ri-row-state mono">{h.local ? "this halo" : presence(h, now)} · {costToday(h, costs?.harnesses.find((x) => x.id === h.id)?.usd)}</span>
            </button>
            <Button size="sm" variant="ghost" onClick={() => pickLive("machine", h.id)} aria-label={`Open ${h.name || h.id}`}>Open</Button>
          </li>
        ))}
      </ul>
    </div>
  );
}
