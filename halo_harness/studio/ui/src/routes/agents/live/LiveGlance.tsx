// Agents -> Live's inspector with nothing picked: this halo at a glance, summary first -- the agents working, the
// decisions waiting on you (amber; a click opens Attention), what its sessions spent today, the caps reached (Lift).
import type { ReactNode } from "react";
import { cost } from "../../orchestra/format";
import { balanceLines, Reached, Ticker, useCosts } from "../../fleet/Costs";
import { useAttnCount, usePanels } from "../../fleet/pstore";
import { useCounts } from "../../fleet/store";
import { toggleAttention } from "../attention";

function Line({ k, children, tone, testid }: { k: string; children: ReactNode; tone?: "warn"; testid?: string }) {
  return (
    <div data-line={k} data-tone={tone} data-testid={testid}>
      <dt className="mono">{k}</dt>
      <dd>{children}</dd>
    </div>
  );
}

export function LiveGlance() {
  useCosts();
  const c = useCounts();
  const waiting = useAttnCount(c.attention);
  const costs = usePanels((s) => s.costs);
  const cap = costs?.caps?.per_harness_usd_per_day;
  return (
    <div className="ri-sum lv-glance" data-testid="live-glance">
      <dl className="ri-summary" data-testid="live-glance-lines">
        <Line k="working">{c.live} agent{c.live === 1 ? "" : "s"} of {c.agents} in {c.sessions} session{c.sessions === 1 ? "" : "s"}</Line>
        <Line k="waits on you" tone={waiting ? "warn" : undefined} testid="live-glance-waiting">
          {waiting ? <button className="og-link mono" onClick={toggleAttention}>{waiting} decision{waiting === 1 ? "" : "s"} (Attention, A)</button> : "nothing"}
        </Line>
        <Line k="spent today" testid="live-glance-spend">
          {costs ? <><Ticker usd={costs.total} />{cap ? ` of ${cost(cap)} cap` : " · no cap"}</> : "reading today's spend..."}
        </Line>
      </dl>
      {costs && balanceLines(costs.balances).length > 0 && <div className="fco-bal mono muted" data-testid="live-glance-balances">{balanceLines(costs.balances).join(" · ")}</div>}
      {costs && <Reached c={costs} />}
    </div>
  );
}
