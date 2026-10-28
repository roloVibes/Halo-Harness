// session-cost (3.1.4.0 R2; 3.1.5.0 R3 "Cost that reads"): what the chosen
// session (else the newest live one on this harness) has cost so far, from
// the rows the Fleet store already holds (GET fleet and its feed; the
// session row's status figures and each agent row's own tokens, from
// fleet/local_view.py): the spend ticking up with its sparkline beside it
// (spend.ts), the context-fill bar, the tokens in and out, the turns and the
// cost per turn (the average, and what the last turn cost), the time since
// it started, the model, and each agent's share of the spend as one stacked
// bar over its rows (CostParts.tsx). The compact face is the spend and the tokens.
// 3.1.8.0 R6: the session's figures move on its own `message_end` / `status`
// frames, the event the terminal's status bar moves on (fleet/figures.ts);
// TURNS is one unit, the session's user turns (an agent row's own count is its
// model calls, shown as "calls" on its line); each agent's share is its own
// spend, a finished sub-agent counted once (shares.ts).
// 3.3.3.1: the spend is the priced part; when some model reports no price
// (`cost_complete === false`) the ticker and PER TURN carry a "+" whose title
// names the model, and main's line says "no price" when its own model is one.
import { useEffect } from "react";
import type { MotionState } from "../../lib/motion";
import { Empty } from "../../lib/ui";
import { Metric } from "../orchestra/bits";
import { cost, short } from "../orchestra/format";
import { useTicker } from "../fleet/MapNode";
import { isLive, keyOf, sessionMotion, sessionTitle, useFleet, useNow } from "../fleet/store";
import type { SessionRow } from "../fleet/types";
import { hueOf } from "../shared/hues";
import { AgentLine, ContextBar, ShareBar, Spark, tok, type Share } from "./CostParts";
import { lastTurnCost, startSpend, useSpend } from "./spend";
import { ownCosts, partialTitle, unpricedMain } from "./shares";
import { chosenSession } from "./store";

/** 45s, 12m 03s, 2h 05m since a unix time in seconds. */
function since(ts: number | null | undefined, now: number): string {
  if (!ts) return "-";
  const s = Math.max(0, Math.floor(now / 1000 - Number(ts)));
  if (s < 60) return `${s}s`;
  if (s < 3600) return `${Math.floor(s / 60)}m ${String(s % 60).padStart(2, "0")}s`;
  return `${Math.floor(s / 3600)}h ${String(Math.floor((s % 3600) / 60)).padStart(2, "0")}m`;
}

const modelName = (m: string | null | undefined) => String(m || "").replace(/^[a-z]+:/, "").split("/").pop() || "-";

/** The session's user turns (the terminal's turn count), never an agent's model calls. */
function turnsOf(ss: SessionRow): number | null {
  return typeof ss.turns === "number" && ss.turns > 0 ? ss.turns : null;
}

/** The spend; `partial` (3.3.3.1: some model reports no price) adds a "+" and says so in the title. */
function Ticker({ usd, partial = "" }: { usd: number; partial?: string }) {
  const shown = useTicker(usd);
  return (
    <span className="sco-ticker mono" data-testid="session-cost-usd" title={partial || undefined}>
      {cost(shown)}
      {partial && <span className="sco-partial" data-testid="session-cost-partial" title={partial}>+</span>}
    </span>
  );
}

function Figure({ label, value, testid, title }: { label: string; value: string; testid: string; title?: string }) {
  return (
    <div className="sco-fig" title={title}>
      <span className="sco-label mono">{label}</span>
      <b className="sco-value mono" data-testid={testid}>{value}</b>
    </div>
  );
}

export function CostDetail() {
  useEffect(() => startSpend(), []);
  const ss = useFleet(chosenSession);
  const hid = useFleet((s) => s.scope.harness || "");
  const now = useNow(!!ss, 1000);
  const series = useSpend(ss?.session_id || "");
  if (!ss) return <Empty title="No session here yet" body="Start one in a terminal (halo): what it spends, its tokens and its turns show here as it works." testid="session-cost-empty" />;
  const usd = Number(ss.cost_usd) || 0;
  const own = ownCosts(ss);
  const partial = partialTitle(ss);
  const noPrice = unpricedMain(ss, own);
  const agents = [...(ss.agents || [])].sort((a, b) => (own.get(b.agent_id) || 0) - (own.get(a.agent_id) || 0));
  const spent = agents.reduce((s, a) => s + (own.get(a.agent_id) || 0), 0);
  const shares: Share[] = agents.map((a) => {
    const key = keyOf(hid, ss.session_id, a.agent_id);
    const v = own.get(a.agent_id) || 0;
    return { a, key, hc: hueOf(key), usd: v, pct: spent > 0 ? (v / spent) * 100 : 0, noPrice: a.agent_id === noPrice };
  });
  const live = agents.filter(isLive).length;
  const turns = turnsOf(ss);
  const perTurn = turns ? usd / turns : null;
  const last = lastTurnCost(series);
  return (
    <div className="sco" data-testid="session-cost-detail" data-session={ss.session_id}>
      <div className="rail-label mono sco-head" title={ss.cwd || ""}>THIS SESSION · {short(sessionTitle(ss), 48)}</div>
      <div className="sco-sub mono muted">
        <span data-testid="session-cost-model" title={ss.model || ""}>{short(modelName(ss.model), 22)}</span>
        {ss.effort ? <span data-testid="session-cost-effort" data-na={ss.effort === "effort n/a" || undefined}
                           title="what the effort level does on this model"> · {ss.effort}</span> : null}
        <span title="since the session started"> · <span data-testid="session-cost-elapsed">{since(ss.started, now)}</span></span>
        <span> · <span data-testid="session-cost-agents">{`${live} live of ${agents.length}`}</span></span>
      </div>
      <div className="sco-top">
        <Ticker usd={usd} partial={partial} />
        <Spark list={series} />
      </div>
      <ContextBar used={ss.context_tokens} limit={ss.context_limit} />
      <div className="sco-grid">
        <Figure label="TOKENS IN" value={tok(ss.tokens_in)} testid="session-cost-in" title="input tokens the session has sent its model so far" />
        <Figure label="TOKENS OUT" value={tok(ss.tokens_out)} testid="session-cost-out" title="output tokens its model has written so far" />
        <Figure label="TURNS" value={turns == null ? "-" : String(turns)} testid="session-cost-turns" title="your turns in this session, as the terminal counts them" />
        <Figure label="PER TURN" value={perTurn == null ? "-" : `${cost(perTurn)}${partial ? "+" : ""}`} testid="session-cost-per-turn"
                title={`the spend over your turns${last != null ? `; the last turn cost ${cost(last)}` : ""}${partial ? `; ${partial}` : ""}`} />
      </div>
      {agents.length > 0 && (
        <section className="sco-agents">
          <div className="rail-label mono sco-agents-head">
            <span>EACH AGENT'S SHARE</span>
            <span className="muted">tokens in / out · calls · own cost</span>
          </div>
          <ShareBar rows={shares} />
          {shares.slice(0, 9).map((r) => <AgentLine key={r.key} r={r} />)}
        </section>
      )}
    </div>
  );
}

export function CostGlance() {
  const ss = useFleet(chosenSession);
  if (!ss) return <div className="glance"><div className="glance-text">No session here yet</div><div className="glance-hint">Run halo in a terminal.</div></div>;
  return (
    <div className="glance" data-testid="session-cost-glance">
      <div className="glance-numbers">
        <Metric value={<Ticker usd={Number(ss.cost_usd) || 0} partial={partialTitle(ss)} />} label="this session" tone="accent" />
        <Metric value={tok((Number(ss.tokens_in) || 0) + (Number(ss.tokens_out) || 0))} label="tokens" />
      </div>
      <div className="glance-hint mono">{modelName(ss.model)}</div>
    </div>
  );
}

export function useCostMotion(): MotionState {
  const ss = useFleet(chosenSession);
  return ss ? (sessionMotion(ss) === "working" ? "working" : "idle") : "none";
}
