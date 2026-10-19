// session-cost (3.1.4.0 R2): what the chosen session (else the newest live
// one on this harness) has cost so far, from the rows the Fleet store already
// holds (GET fleet and its feed; the session row's status figures, from
// fleet/local_view.py): the spend ticking up, the tokens in and out, the
// turns, the time since it started, the model, and what each of its agents
// has cost. The compact face is the spend and the tokens.
import type { MotionState } from "../../lib/motion";
import { Empty } from "../../lib/ui";
import { Metric } from "../orchestra/bits";
import { cost, short } from "../orchestra/format";
import { useTicker } from "../fleet/MapNode";
import { isLive, sessionMotion, sessionTitle, useFleet, useNow } from "../fleet/store";
import type { SessionRow } from "../fleet/types";
import { chosenSession } from "./store";

/** 12, 4.3k, 1.2M. */
function tok(n: number | null | undefined): string {
  if (n == null || !isFinite(Number(n))) return "-";
  const v = Number(n);
  return v >= 1e6 ? `${(v / 1e6).toFixed(1)}M` : v >= 1e3 ? `${(v / 1e3).toFixed(1)}k` : String(Math.round(v));
}

/** 45s, 12m 03s, 2h 05m since a unix time in seconds. */
function since(ts: number | null | undefined, now: number): string {
  if (!ts) return "-";
  const s = Math.max(0, Math.floor(now / 1000 - Number(ts)));
  if (s < 60) return `${s}s`;
  if (s < 3600) return `${Math.floor(s / 60)}m ${String(s % 60).padStart(2, "0")}s`;
  return `${Math.floor(s / 3600)}h ${String(Math.floor((s % 3600) / 60)).padStart(2, "0")}m`;
}

const modelName = (m: string | null | undefined) => String(m || "").replace(/^[a-z]+:/, "").split("/").pop() || "-";

function turnsOf(ss: SessionRow): number | null {
  if (typeof ss.turns === "number") return ss.turns;
  const main = (ss.agents || []).find((a) => !a.parent);
  return typeof main?.turns === "number" ? main.turns : null;
}

function Ticker({ usd }: { usd: number }) {
  const shown = useTicker(usd);
  return <span className="sco-ticker mono" data-testid="session-cost-usd">{cost(shown)}</span>;
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
  const ss = useFleet(chosenSession);
  const now = useNow(!!ss, 1000);
  if (!ss) return <Empty title="No session here yet" body="Start one in a terminal (halo): what it spends, its tokens and its turns show here as it works." testid="session-cost-empty" />;
  const agents = [...(ss.agents || [])].sort((a, b) => (Number(b.cost_usd) || 0) - (Number(a.cost_usd) || 0));
  const live = agents.filter(isLive).length;
  const turns = turnsOf(ss);
  return (
    <div className="sco" data-testid="session-cost-detail" data-session={ss.session_id}>
      <div className="rail-label mono sco-head" title={ss.cwd || ""}>THIS SESSION · {short(sessionTitle(ss), 48)}</div>
      <Ticker usd={Number(ss.cost_usd) || 0} />
      <div className="sco-grid">
        <Figure label="TOKENS IN" value={tok(ss.tokens_in)} testid="session-cost-in" title="input tokens the session has sent its model so far" />
        <Figure label="TOKENS OUT" value={tok(ss.tokens_out)} testid="session-cost-out" title="output tokens its model has written so far" />
        <Figure label="TURNS" value={turns == null ? "-" : String(turns)} testid="session-cost-turns" />
        <Figure label="ELAPSED" value={since(ss.started, now)} testid="session-cost-elapsed" title="since the session started" />
        <Figure label="MODEL" value={short(modelName(ss.model), 22)} testid="session-cost-model" title={ss.model || ""} />
        <Figure label="AGENTS" value={`${live} live of ${agents.length}`} testid="session-cost-agents" />
      </div>
      {agents.length > 0 && (
        <section className="sco-agents">
          <div className="rail-label mono">PER AGENT</div>
          {agents.slice(0, 8).map((a) => (
            <div key={a.agent_id} className="sco-row" data-state={a.state || "none"} data-testid="session-cost-agent">
              <span>{short(a.name || a.role || a.agent_id, 26)}</span>
              <span className="mono muted">{a.state}</span>
              <b className="mono">{cost(a.cost_usd)}</b>
            </div>
          ))}
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
        <Metric value={<Ticker usd={Number(ss.cost_usd) || 0} />} label="this session" tone="accent" />
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
