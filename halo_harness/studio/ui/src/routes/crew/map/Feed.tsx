// "What they think and say" (3.6.0.0 R4, the design's feed drawer): the lit session's rows -- THINK, SAY, TALK (agent to
// agent, its own label), a tool, an ask -- from the same live feed Session's Live column reads (shared/liveFeed.ts) and
// drawn by the same rows (session/LiveRows.tsx: an ask's answers are its buttons, the Attention row's own), newest at the
// bottom with the follow rule Session's Live uses (session/follow.ts: scroll up to stop following, the pill to follow
// again). Filtered by the clicked box (or a helper), or everyone. At its foot: Steer (a text box that fits its text) and
// Stop, both to the agent of the clicked box (main for everyone) -- the owner's own controls, said plainly.
import { useCallback, useMemo, useRef, useState } from "react";
import { Button, Empty, TextBox } from "../../../lib/ui";
import { agentCommand, steer } from "../../fleet/actions";
import { hueOf } from "../../shared/hues";
import { useLive, type LiveLine } from "../../shared/liveFeed";
import { LiveRow, type Who } from "../../session/LiveRows";
import { useFollow } from "../../session/follow";
import { followAgain } from "../../session/steer";
import { setFeedFor, useLitStore } from "./litStore";
import { useLitNow } from "./useLit";

const VIEW = 300;
const noop = () => undefined;

export function Feed() {
  const L = useLitNow();
  const filter = useLitStore((s) => s.feedFor);
  const all = useLive((s) => s.lines);
  const scroller = useRef<HTMLDivElement>(null);
  const [text, setText] = useState("");
  const [stopping, setStopping] = useState(false);
  const agents = useMemo(() => L.rec?.agents || [], [L.rec]);
  const who = useMemo(() => new Map<string, Who>(agents.map((a) => [a.key, { name: a.name, hc: hueOf(a.key), state: a.state, model: a.model }])), [agents]);
  const ids = useMemo(() => {
    if (!filter) return null;
    if (filter.startsWith("agent:")) return new Set([filter.slice(6)]);
    return new Set(L.ov?.boxes[filter]?.agents || []);
  }, [filter, L.ov]);
  const keys = useMemo(() => new Set(agents.filter((a) => !ids || ids.has(a.id)).map((a) => a.key)), [agents, ids]);
  // a TALK row shows for both its speaker and its listener (main handing the box its task is the box's too)
  const lines = useMemo(() => all.filter((l) => keys.has(l.key) || (!!l.talk && (keys.has(l.talk.toKey) || keys.has(l.talk.fromKey)))), [all, keys]);
  const shown = useMemo(() => (lines.length > VIEW ? lines.slice(-VIEW) : lines), [lines]);
  const { following, fresh, onScroll } = useFollow(scroller, shown);
  const target = agents.find((a) => ids?.has(a.id) && ["running", "waiting", "queued", "paused"].includes(a.state))
    || agents.find((a) => ids?.has(a.id)) || agents.find((a) => a.id === "main");
  const onPin = useCallback((k: string) => { const a = agents.find((x) => x.key === k); if (a) setFeedFor(`agent:${a.id}`); }, [agents]);
  const lastN = shown[shown.length - 1]?.n;
  const boxes = Object.entries(L.ov?.boxes || {}).filter(([, b]) => b.agents.length);
  if (L.mode === "replay") return <Empty title="A replay" body="What the agents thought and said in a past run is in its report card (History, under the map)." testid="map-feed-replay" />;
  if (L.mode === "off" || !L.session) return <Empty title="Nothing runs on this map now" body="Start a session on it: what its agents think and say lands here as it happens." testid="map-feed-none" />;
  const send = async () => {
    if (target && text.trim() && (await steer(target.key, text, "nudge"))) setText("");
  };
  return (
    <div className="mpf" data-testid="map-feed" data-filter={filter || "everyone"} data-follow={following || undefined}>
      <label className="mpf-pick">
        <span className="cw-line">Show</span>
        <select className="input" value={filter} onChange={(e) => setFeedFor(e.target.value)} data-testid="map-feed-filter" aria-label="Whose words to show">
          <option value="">everyone</option>
          {boxes.map(([id]) => <option key={id} value={id}>{id === "main" ? "main" : `the box ${id}`}</option>)}
          {(L.ov?.helpers || []).map((h) => <option key={h.aid} value={`agent:${h.aid}`}>{h.name} (made up)</option>)}
          {filter.startsWith("agent:") && !(L.ov?.helpers || []).some((h) => `agent:${h.aid}` === filter) && <option value={filter}>{filter.slice(6)}</option>}
        </select>
      </label>
      <div className="mpf-rows slv-scroll" ref={scroller} onScroll={onScroll} data-testid="map-feed-scroll" tabIndex={-1}>
        {!shown.length && <Empty title="Nothing said yet" body="Each thought, words, a tool call, a hand-off between agents and an ask land here the moment they happen." testid="map-feed-empty" />}
        {shown.map((l: LiveLine) => (
          <LiveRow key={l.n} l={l} who={who.get(l.key) || { name: l.key.split("|")[2] || "?", hc: hueOf(l.key), state: "" }} last={l.n === lastN} target={false}
                   onPin={onPin} onHover={noop} onTarget={noop} />
        ))}
      </div>
      {fresh > 0 && <button type="button" className="slv-new mono" data-testid="map-feed-follow" onClick={followAgain}>{fresh} new row{fresh === 1 ? "" : "s"} · follow</button>}
      {target && (
        <footer className="mpf-foot" data-testid="map-feed-controls" data-target={target.id}>
          <TextBox value={text} onChange={(e) => setText(e.target.value)} placeholder={`Steer ${target.name}: what it reads before its next step`}
                   aria-label={`Steer ${target.name}`} data-testid="map-feed-steer-text"
                   onKeyDown={(e) => { if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) { e.preventDefault(); void send(); } }} />
          <span className="mpf-buttons">
            <Button variant="primary" onClick={() => void send()} disabled={!text.trim()} data-testid="map-feed-steer">Steer {target.name}</Button>
            {!stopping ? <Button onClick={() => setStopping(true)} data-testid="map-feed-stop">Stop {target.name}</Button> : (
              <span className="mpf-ask" data-testid="map-feed-stop-ask">
                <span className="cw-line">Stop {target.name} at its next step?</span>
                <Button variant="primary" data-testid="map-feed-stop-yes"
                        onClick={() => { setStopping(false); void agentCommand(target.key, "stop", { reason: "stopped from Studio" }); }}>Yes, stop it</Button>
                <Button onClick={() => setStopping(false)}>No</Button>
              </span>
            )}
          </span>
        </footer>
      )}
    </div>
  );
}
