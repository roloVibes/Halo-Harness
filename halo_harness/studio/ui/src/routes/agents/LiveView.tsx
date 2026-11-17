// Agents -> 4 · Live (3.6.0.2 R52 R3 R34: "what a session is doing now, drawn on the map it really follows"): the view bar
// (the four-tab switch, then Attention, as every tab), a workspace `agents-live` with one main panel titled WORDS.live.
// In it, in this order: the picker "Which session" (only with two or more open sessions: this machine's, then other
// machines'; livePick.ts; its row's room is reserved from the first draw, so a second session opening moves nothing,
// R12), the session's T-state line and its status line (LiveHead.tsx, from its row at once), then the frame: for a local session with a map, its drawing (LiveDraw.tsx); for one with no map (T4), one that ended (T8), one on
// another machine (T9), one with no message yet (T10) or none (Empty) the frame stays empty at its reserved height and
// nothing is fetched (R28). R57: its right drawer titled WORDS.feed is the Feed (crew/map/Feed.tsx) for Live's session
// (liveLit.tsx), closed until he opens it from the view bar or a door opens it (crew/map/feedOpen.ts openFeed).
import { useEffect } from "react";
import { Empty } from "../../lib/ui";
import { Workspace } from "../../lib/workspace/Workspace";
import type { PanelSpec } from "../../lib/workspace/types";
import { Feed } from "../crew/map/Feed";
import { FEED_PANEL, LIVE_SECTION } from "../crew/map/feedOpen";
import { startLit } from "../crew/map/litStore";
import { truthLines, truthState, WORDS } from "../crew/map/truth";
import { useLitNow } from "../crew/map/useLit";
import { AttentionChip } from "./AttentionChip";
import { LiveRun } from "./LiveDraw";
import { LiveHead } from "./LiveHead";
import { LiveLit, liveRun } from "./liveLit";
import { pickLive, useLivePick } from "./livePick";
import { ViewSwitch } from "./ViewSwitch";

export { LIVE_SECTION };

function LiveMain() {
  useEffect(() => startLit(), []);
  const p = useLivePick();
  const st = truthState(p.f);
  const run = liveRun(p);
  return (
    <div className="ag-live" data-testid="agents-live" data-sid={p.sid} data-map={p.f.a || ""} data-state={st}>
      <div className="ag-live-pickrow" data-testid="live-pickrow">{/* R12: its room is kept from the first draw */}
        {p.opts.length > 1 && (
          <select className="ag-live-pick" data-testid="live-pick" aria-label="Which session" value={p.value}
                  onChange={(e) => pickLive(e.currentTarget.value, !p.opts.find((o) => o.sid === e.currentTarget.value)?.away)}>
            {!p.opts.some((o) => o.sid === p.value) && <option value={p.value}>{p.f.title}</option>}
            {p.opts.map((o) => <option key={o.sid} value={o.sid}>{o.text}</option>)}
          </select>
        )}
      </div>
      {run ? <LiveRun key={run.sid} s={run} f={p.f} /> : (
        <>
          <LiveHead f={p.f} sid={p.sid} />
          <div className="ag-live-frame" data-testid="live-frame" />
        </>
      )}
    </div>
  );
}

export const livePanels: PanelSpec[] = [
  { id: "live-main", testid: "agents-live-panel", title: WORDS.live, role: "main",
    about: "What a session is doing now, drawn on the map it really follows.",
    help: "The session Session shows: which map it runs on, and what its agents do now.",
    face: "detail", glance: LiveMain, detail: LiveMain },
  { id: FEED_PANEL, testid: "live-feed-panel", title: WORDS.feed, role: "drawer", side: "right", contentW: 420,
    about: `What the agents of the session ${WORDS.live} shows say and do, line by line: thoughts, words, tools, hand-offs to other agents and asks, newest at the bottom.`,
    help: `Click a box in ${WORDS.live}: only its agents (or pick everyone).\nSteer: a few words the agent reads before its next step.\nStop: it stops at its next step.\nAn ask's answers are its buttons.`,
    face: "detail", glance: FeedGlance, detail: LiveFeed },
];

/** R57: the Feed of Live's session; with none here (another machine's, or none open), the T-state says why. */
function LiveFeed() {
  const L = useLitNow();
  const p = useLivePick();
  if (L.session) return <Feed />;
  return <Empty title={truthLines(p.f)[0]?.text || ""} body="What its agents think and say lands here as it happens." testid="map-feed-none" />;
}

function FeedGlance() {
  const L = useLitNow();
  const p = useLivePick();
  return <div className="glance"><div className="glance-hint">{L.session ? "What the agents think and say: expand it, or click a box." : truthLines(p.f)[0]?.text}</div></div>;
}

export function LiveView() {
  const lead = (
    <span className="cw-lead">
      <ViewSwitch view="live" />
      <AttentionChip />
    </span>
  );
  return (
    <div className="cw" data-testid="live-view">
      <LiveLit><Workspace section={LIVE_SECTION} specs={livePanels} lead={lead} /></LiveLit>
    </div>
  );
}
