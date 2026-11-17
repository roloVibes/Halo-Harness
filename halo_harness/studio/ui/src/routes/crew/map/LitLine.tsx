// The lit Map's top line (3.6.0.0 R4, the design: "A session is running on this map (started 14:02), then the one
// sentence"): which session lights the map and when it started; the one sentence of what goes on (agents/live/narrate.ts,
// computed from the same rows and waits Live used -- who works, who waits on what or on you, the models, dollars so
// far); when an edit takes effect; in amber, a session that runs on ANOTHER map with "Show the running map"; a picker
// when more than one session runs; a session that did not start on a map said so; a Builder card the session parked
// ("answer it in the session"); a box that landed under "Not connected yet" with a link that brings the strip into view.
// 3.6.0.0 R4b: the sentence's wait is a link (the box into view, opened in the drawer); "plan: 3 of 7 done"; a goal run
// going, with Open; with nothing running, "Replay the last session"; another machine's session listed in the picker.
import { useEffect, useMemo } from "react";
import { Button } from "../../../lib/ui";
import { goSection } from "../../../lib/store";
import { fleet } from "../../fleet/store";
import { isLiveRun, useOrch } from "../../orchestra/store";
import { openRun as openOrchRun, startOrchestra } from "../../orchestra/sync";
import { openFeed, openMapDrawer } from "./feedOpen";
import { boxOfAgent } from "./talkPulse";
import { planWords, startTodos, useTodos } from "./todoStore";
import { liveNodes, type LiveNode } from "../live/liveModel";
import { narrate } from "../live/narrate";
import { useWaits } from "../live/useWaits";
import { closeRun, replayRun, useMapHist } from "./mapRuns";

/** R4b (R4's gap 9): with nothing running and a finished run in History, the top line offers to replay it. */
export function ReplayLast() {
  const last = useMapHist((s) => s.rows[0]);
  return last ? <> <Button size="sm" onClick={() => void replayRun(last.sid)} data-testid="map-lit-replay-last" title={`Replay "${last.what.slice(0, 60)}" on the map`}>Replay the last session</Button></> : null;
}
import { pickSession } from "./litStore";
import { openMap, useMap } from "./mapStore";
import { useLitNow, type Lit } from "./useLit";

export const WHEN_WORDS = "Edits stay allowed: a line, a When or a new box take effect at the next hand-off; an agent's own change the next time that agent starts; main's model and instructions with the next session.";
const clock = (t: number) => (t ? new Date(t * 1000).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }) : "");

type Sentence = { text: string; head: string; tail: string; wait: string; leaf: string };

/** R4b (R4's gap 6 and 9): a click on the sentence's wait brings the box it names into view and opens it in the drawer. */
export function showWaited(L: Lit, leaf: string): void {
  if (!L.ov || !leaf) return;
  const box = boxOfAgent(L.ov).get(leaf) || "";
  if (!box) return;
  openFeed(box.startsWith("made-up:") ? `agent:${box.slice(8)}` : box);
  const el = document.querySelector<HTMLElement>(`[data-testid=map-world] [data-map-box="${CSS.escape(box)}"]`);
  el?.scrollIntoView({ block: "center", inline: "center" });
  el?.focus({ preventScroll: true });
}

function useSentence(L: Lit): Sentence {
  const nodes: LiveNode[] = useMemo(() => (L.rec ? liveNodes(L.rec, fleet.get(), L.now * 1000) : []), [L.rec, L.now]);
  const { waits, path } = useWaits(nodes, L.now * 1000, L.mode === "live" && !L.other);
  const box = useMemo(() => {
    const m = new Map<string, string>();
    for (const [id, b] of Object.entries(L.ov?.boxes || {})) for (const a of b.agents) m.set(a, id === "main" ? "" : id);
    for (const h of L.ov?.helpers || []) m.set(h.aid, `${h.box === "main" ? "main" : h.box}'s helpers`);
    return m;
  }, [L.ov]);
  const n = narrate(nodes, waits, path, (x) => box.get(x.id) || "");
  const at = n.head.indexOf("waiting on");
  const end = at < 0 ? -1 : n.head.indexOf(";", at);
  return at < 0 || !path.leaf ? { text: n.text, head: n.text, tail: "", wait: "", leaf: "" }
    : { text: n.text, head: n.head.slice(0, at), wait: n.head.slice(at, end < 0 ? undefined : end), tail: (end < 0 ? "" : n.head.slice(end)) + n.tail, leaf: path.leaf.id };
}

function Picker({ L }: { L: Lit }) {
  if (L.all.length + L.away.length < 2) return null;
  return (
    <select className="input mp-lit-pick" value={L.session?.sid || ""} onChange={(e) => pickSession(e.target.value)} data-testid="map-lit-pick" aria-label="Which running session lights the map">
      {L.all.map((s) => <option key={s.sid} value={s.sid}>{s.title.slice(0, 40)} ({s.map ? `map ${s.map}` : "not on a map"})</option>)}
      {L.away.map((s) => <option key={s.sid} value={s.sid} disabled>{s.title.slice(0, 40)} (on {s.machine}: open it on that machine)</option>)}
    </select>
  );
}

/** R4b: the session's todo plan ("plan: 3 of 7 done"), a goal run going, each a link into the drawer. */
export function Extras({ L }: { L: Lit }) {
  useEffect(() => (startTodos(), startOrchestra()), []);
  const plan = planWords(useTodos(L.session?.sid || ""));
  const run = useOrch((s) => s.runs.find((r) => isLiveRun(r.state)));
  if (!plan && !run) return null;
  return (
    <span className="cw-line" data-testid="map-lit-extras">
      {plan && <button type="button" className="mp-link" onClick={() => openFeed("plan")} data-testid="map-lit-plan" title="The session's plan, in the drawer">{plan}</button>}
      {plan && run && " · "}
      {run && (
        <span data-testid="map-lit-run" data-run={run.run_id}>
          A goal run is going: {run.goal_what.slice(0, 80)}{" "}
          <Button size="sm" onClick={() => void openOrchRun(run.run_id).then(() => openMapDrawer(`run:${run.run_id}`))} data-testid="map-lit-run-open"
                  title="Its pages (lanes, the gate, the merge, its report) in the drawer">Open</Button>
        </span>
      )}
    </span>
  );
}

export function LitLine() {
  const L = useLitNow();
  const shown = useMap((s) => s.name);
  const card = L.card.some((c) => c.target === `map:${shown}`);
  const sentence = useSentence(L);
  const run = useMapHist((s) => s.open);
  if (L.mode === "replay")
    return (
      <p className="cw-line mp-topline" data-testid="map-topline" data-lit="replay">
        Replaying {run?.title ? `"${run.title.slice(0, 60)}"` : "a past session"} {run?.map ? (run.map === shown ? "on this map" : `(it ran on ${run.map})`) : "(it did not start on a map)"}, in quiet colours.{" "}
        <Button size="sm" onClick={closeRun} data-testid="map-replay-close">Back to now</Button>
      </p>
    );
  if (!L.session) {
    const off = L.all[0];
    return (
      <p className="cw-line mp-topline" data-testid="map-topline">
        Nothing is running on it now.{off ? <> {L.all.length} session{L.all.length === 1 ? "" : "s"} running, not on a map: <Button size="sm" onClick={() => pickSession(off.sid)} data-testid="map-lit-show-nomap">Show it</Button></> : ""}
        {" "}{WHEN_WORDS} <Extras L={L} />
      </p>
    );
  }
  const s = L.session;
  if (L.other)
    return (
      <p className="cw-line mp-topline mp-amber" data-testid="map-topline" data-lit="other">
        A session is running on another map, {s.map} (started {clock(s.started)}); this one is not lit.{" "}
        <Button size="sm" onClick={() => void openMap(s.map || "")} data-testid="map-show-running">Show the running map</Button> <Picker L={L} />
      </p>
    );
  return (
    <div className="mp-topline mp-lit-line" data-testid="map-topline" data-lit={L.nomap ? "nomap" : "live"} data-sid={s.sid}>
      <span className="cw-line" data-testid="map-lit-head">
        {L.nomap ? `This session did not start on a map (started ${clock(s.started)}): main and the helpers it made up, no lines.` : `A session is running on this map (started ${clock(s.started)}).`}
        {L.nomap && <> <Button size="sm" onClick={() => pickSession("")} data-testid="map-lit-back">Show the map again</Button></>}
        <Picker L={L} />
      </span>
      {sentence.text && (
        <span className="cw-line mono" data-testid="map-lit-sentence">
          {sentence.head}
          {sentence.wait && <button type="button" className="mp-wait-link" onClick={() => showWaited(L, sentence.leaf)} data-testid="map-lit-wait" data-leaf={sentence.leaf}
                                    title="Bring the box it waits on into view, and open it in the drawer">{sentence.wait}</button>}
          {sentence.tail}
        </span>
      )}
      <Extras L={L} />
      {!L.nomap && <span className="cw-line" data-testid="map-lit-when">{WHEN_WORDS}</span>}
      {card && (
        <span className="cw-line mp-amber" data-testid="map-lit-card">
          The session asks to change this map (drawn dashed): answer it in the session.{" "}
          <Button size="sm" onClick={() => goSection("session")} data-testid="map-lit-card-go">Go to the session</Button>
        </span>
      )}
    </div>
  );
}
