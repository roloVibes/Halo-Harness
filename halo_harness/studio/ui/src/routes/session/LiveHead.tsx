// The Live column's header row (3.1.5.0 R3; 3.1.7.0 R1 Fleet's filters in
// the column): LIVE, how many agents work and how many lines it holds, the
// "only <agent>" chip while one is pinned, then the agent pick ("every agent"
// and each agent of the session, in tree order; it is the pin, so a tag, a
// lane or the map's steer chip moves it too), the kind pick ("every kind",
// tools, text, states, asks; a steer you send always shows) and Follow. The
// picks are the Activity log's `.fac-pick` selects. 3.3.0.0 R6: Follow shows
// whether the column follows now (off while you compose in the Steer field),
// and Export downloads the session's trace (TraceExport.tsx).
// 3.3.16.2: think and talk in the kind pick; Thinking beside Follow (only thoughts and their acts).
// 3.3.7.0 R2: the offline-promise chip (OfflineChip.tsx) for a session of this harness. 3.4.1.0 R3: the mode word (ModeWord.tsx).
// 3.3.6.0 R6: Screenshot captures the display of the machine the session's harness runs on and attaches it to the
// next steer (steerImage.ts): from a Mac or Kali driving this Studio, it is this PC's screen.
import { Button, Icon } from "../../lib/ui";
import { short } from "../orchestra/format";
import { fleet, findAgent, useFleet } from "../fleet/store";
import type { LiveKind, LiveLine } from "../shared/liveFeed";
import { OfflineChip } from "./OfflineChip";
import { ModeWord } from "./ModeWord";
import { pinTo, useStripAgents } from "./steer";
import { takeScreenshot, useSteerImage } from "./steerImage";
import { chosenSession, sess, useSession } from "./store";
import { TraceExport } from "./TraceExport";

/** The kind pick's choices: value, label, the line kinds it keeps. */
export const KIND_PICKS: [string, string, LiveKind[]][] = [
  ["tool", "tools", ["tool"]],
  ["text", "text", ["text", "output", "asked"]],
  ["think", "think", ["thinking"]], // 3.3.16.2: thoughts, and agents' words to each other
  ["talk", "talk", ["talk"]],
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

/** 3.3.16.2: Live narrowed to one pair's talk (Conversations' "show in Live"); the chip shows everything again. */
function PairChip() {
  const pair = useSession((s) => s.pair);
  if (!pair) return null;
  const name = (k: string) => (k.startsWith("machine:") ? k.slice(8) : findAgent(fleet.get(), k)?.a.name || k.split("|")[2] || "?");
  const [a, b] = pair.split(">");
  return (
    <button type="button" className="slv-pinned mono" data-testid="live-pair-chip" onClick={() => sess.update(() => ({ pair: "" }))} title="Show every row again">
      only {short(name(a), 14)} ↔ {short(name(b), 14)} <Icon name="close" size={12} />
    </button>
  );
}

/** 3.3.16.2: the Thinking view -- only thoughts and what each led to, for everyone or the pinned agent. */
function ThinkToggle() {
  const on = useSession((s) => s.think);
  return (
    <Button size="sm" variant={on ? "primary" : "ghost"} icon={<Icon name="pulse" />} aria-pressed={on} data-testid="live-think-view"
            onClick={() => sess.update((s) => ({ think: !s.think, follow: true }))} title="Only the thoughts and what each one led to (again: every row)">
      Thinking
    </Button>
  );
}

function ShotButton() {
  const ss = useFleet(chosenSession);
  const hid = useFleet((s) => s.scope.harness || "local");
  const busy = useSteerImage((s) => s.busy);
  return (
    <Button size="sm" variant="ghost" icon={<Icon name="eye" />} disabled={!ss || busy} data-testid="session-live-screenshot"
            onClick={() => ss && void takeScreenshot(hid, ss.session_id, ss.model)}
            title={!ss ? "No session to attach a screenshot to" : "Capture the screen of the machine this session's harness runs on (a Mac " +
              "or Kali driving this Studio captures this PC's screen) and attach it to your next steer"}>
      {busy ? "Capturing..." : "Screenshot"}
    </Button>
  );
}

function OfflineSlot() {
  const ss = useFleet(chosenSession);
  const local = useFleet((s) => (s.scope.harness || "local") === "local");
  return local ? <OfflineChip sid={ss?.session_id} /> : null;
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
      <PairChip />
      <ModeWord />
      <OfflineSlot />
      <span className="spacer" />
      <div className="fac-filters slv-picks">
        <AgentPick />
        <KindPick />
        <Button size="sm" variant={follow ? "primary" : "ghost"} icon={<Icon name="follow" />} aria-pressed={follow} data-testid="session-live-follow"
                onClick={onFollow} title="Keep the newest line in view; scrolling up pauses it">
          Follow
        </Button>
        <ThinkToggle />
        <ShotButton />
        <TraceExport where="head" />
      </div>
    </header>
  );
}
