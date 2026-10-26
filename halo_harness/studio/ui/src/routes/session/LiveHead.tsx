// The Live column's header row (3.1.5.0 R3; 3.1.7.0 R1 Fleet's filters in
// the column): LIVE, how many agents work and how many lines it holds, the
// "only <agent>" chip while one is pinned, then the agent pick ("every agent"
// and each agent of the session, in tree order; it is the pin, so a tag, a
// lane or the map's steer chip moves it too), the kind pick ("every kind",
// tools, text, states, asks; a steer you send always shows) and Follow. The
// picks are the Activity log's `.fac-pick` selects. 3.3.0.0 R6: Follow shows
// whether the column follows now (off while you compose in the Steer field),
// and Export downloads the session's trace (TraceExport.tsx).
import { Button, Icon } from "../../lib/ui";
import { short } from "../orchestra/format";
import { fleet, findAgent } from "../fleet/store";
import type { LiveKind, LiveLine } from "../shared/liveFeed";
import { pinTo, useStripAgents } from "./steer";
import { sess, useSession } from "./store";
import { TraceExport } from "./TraceExport";

/** The kind pick's choices: value, label, the line kinds it keeps. */
export const KIND_PICKS: [string, string, LiveKind[]][] = [
  ["tool", "tools", ["tool"]],
  ["text", "text", ["text", "thinking", "output", "asked"]],
  ["state", "states", ["state", "spawn", "error"]],
  ["ask", "asks", ["ask"]],
];

/** The kind pick as a line filter; a YOU line (your own steer) always passes. */
export function kindIn(pick: string): (l: LiveLine) => boolean {
  const keep = KIND_PICKS.find(([v]) => v === pick)?.[2];
  return keep ? (l) => l.kind === "you" || keep.includes(l.kind) : () => true;
}

function AgentPick() {
  const pin = useSession((s) => s.pin);
  const rows = useStripAgents();
  const known = !pin || rows.some((r) => r.key === pin);
  const extra = known ? null : findAgent(fleet.get(), pin);
  return (
    <label className="fac-pick" title="every agent, or only one (the same as clicking its tag)">
      <select value={pin} aria-label="agent" onChange={(e) => pinTo(e.target.value)} data-testid="session-live-agent">
        <option value="">every agent</option>
        {rows.map((r) => (
          <option key={r.key} value={r.key}>{"· ".repeat(r.depth)}{short(r.a.name || r.a.role || r.a.agent_id, 22)}</option>
        ))}
        {!known && <option value={pin}>{short(extra?.a.name || pin.split("|")[2] || pin, 22)}</option>}
      </select>
    </label>
  );
}

function KindPick() {
  const kind = useSession((s) => s.kind);
  return (
    <label className="fac-pick" title="every kind of line, or only one (your own steers always show)">
      <select value={kind} aria-label="kind" onChange={(e) => sess.update(() => ({ kind: e.target.value, follow: true }))} data-testid="session-live-kind-pick">
        <option value="">every kind</option>
        {KIND_PICKS.map(([v, label]) => <option key={v} value={v}>{label}</option>)}
      </select>
    </label>
  );
}

export function LiveHead({ working, count, onFollow, following }: { working: number; count: number; onFollow: () => void; following: boolean }) {
  const pin = useSession((s) => s.pin);
  const follow = following;
  const pinned = pin ? findAgent(fleet.get(), pin) : null;
  return (
    <header className="slv-head">
      <span className="glance-kicker mono">LIVE</span>
      <span className="mono muted slv-counts" data-testid="session-live-counts">
        {working} working · {count} line{count === 1 ? "" : "s"}
      </span>
      {pinned && (
        <button type="button" className="slv-pinned mono" data-testid="session-live-pinned" onClick={() => pinTo("")} title="Show every agent again (Esc)">
          only {short(pinned.a.name || pinned.a.agent_id, 20)} <Icon name="close" size={12} />
        </button>
      )}
      <span className="spacer" />
      <div className="fac-filters slv-picks">
        <AgentPick />
        <KindPick />
        <Button size="sm" variant={follow ? "primary" : "ghost"} icon={<Icon name="follow" />} aria-pressed={follow} data-testid="session-live-follow"
                onClick={onFollow} title="Keep the newest line in view; scrolling up pauses it">
          Follow
        </Button>
        <TraceExport where="head" />
      </div>
    </header>
  );
}
