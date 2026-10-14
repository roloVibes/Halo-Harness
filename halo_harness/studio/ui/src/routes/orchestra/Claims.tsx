// Claims: the live claims with their holder, state and expiry; Release lets
// the holder's claim go, Steal hands it to the run's lead (the routes'
// own rules answer when that is not possible).
import { useEffect, useState } from "react";
import type { MotionState } from "../../lib/motion";
import { Button } from "../../lib/ui";
import { Metric, NoRun } from "./bits";
import { clock } from "./format";
import { laneColor, useOrch } from "./store";
import { releaseClaim, stealClaim } from "./sync";
import type { Claim } from "./types";

function useNow(ms = 1000): number {
  const [now, setNow] = useState(() => Date.now() / 1000);
  useEffect(() => {
    const id = window.setInterval(() => setNow(Date.now() / 1000), ms);
    return () => window.clearInterval(id);
  }, [ms]);
  return now;
}

function laneOf(holder: string, lanes: { lane: number; holder: string }[]): number | null {
  const m = /^lane:(\d+)$/.exec(holder);
  if (m) return Number(m[1]);
  return lanes.find((l) => l.holder === holder)?.lane ?? null;
}

function Row({ c, now, lane }: { c: Claim; now: number; lane: number | null }) {
  const left = Math.max(0, c.expires - now);
  return (
    <li className="og-claim" data-state={c.state} data-lc={laneColor(lane)} data-motion={c.state === "writing" ? "working" : left < 60 ? "waiting" : "idle"}>
      <div className="og-claim-key mono">{c.key}</div>
      <div className="og-claim-meta mono muted">
        {c.state} · {c.holder} · expires {clock(c.expires)} ({Math.round(left)}s)
      </div>
      <div className="og-claim-actions">
        <Button size="sm" variant="ghost" onClick={() => void releaseClaim(c.key)} title="Let the claim go (the holder's work stays in its worktree)">
          Release
        </Button>
        <Button size="sm" variant="ghost" onClick={() => void stealClaim(c.key)} title="The run's lead takes the unit">
          Steal
        </Button>
      </div>
    </li>
  );
}

export function ClaimsDetail() {
  const data = useOrch((s) => s.data);
  const now = useNow();
  if (!data) return <NoRun what="The claims" />;
  if (!data.claims.length) return <div className="og-wait muted">No live claims. Workers claim units as they join; a finished run holds none.</div>;
  return (
    <ul className="og-claims">
      {data.claims.map((c) => (
        <Row key={c.key} c={c} now={now} lane={laneOf(c.holder, data.lanes)} />
      ))}
    </ul>
  );
}

export function ClaimsGlance() {
  const claims = useOrch((s) => s.data?.claims);
  const lead = useOrch((s) => s.data?.run.lead_holder);
  if (!claims) return <NoRun what="The claims" />;
  const writing = claims.filter((c) => c.state === "writing").length;
  return (
    <div className="glance">
      <div className="glance-numbers">
        <Metric value={claims.length} label="live claims" />
        <Metric value={writing} label="writing" tone="accent" />
      </div>
      <div className="glance-hint mono">lead: {lead || "none recorded"}</div>
    </div>
  );
}

export function useClaimsMotion(): MotionState {
  const claims = useOrch((s) => s.data?.claims);
  if (!claims || !claims.length) return "none";
  return claims.some((c) => c.state === "writing") ? "working" : "idle";
}
