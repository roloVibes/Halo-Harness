// The glance (3.4.1.0 R4; `/?mode=glance`, `halo studio --mode glance`, Studio's "Open the glance"; docs/STUDIO-live.md
// "The glance"): ONE phone-width page of this Studio -- no rail, no panels -- for a look from across the room, or from a
// phone through the SSH door (studio/glance_door.py): the narration sentence (Live's own grammar, narrate.ts, over the
// session Live draws), what waits on you with its answers as large buttons (Asks.tsx), the spend against its cap, the
// elapsed time, the three most recent events. It reconnects by itself and says when it is stale (data.ts). Nothing
// opens by itself; it calls no model; its one write is an answer, through the path Attention's keys take.
import { useEffect } from "react";
import { startAlerts } from "../../lib/alerts";
import { ownerPage } from "../../lib/owner";
import { studio, useStore } from "../../lib/store";
import { paint } from "../../lib/theme";
import { Toasts } from "../../lib/ui";
import { narrate } from "../agents/live/narrate";
import { useLiveNodes } from "../agents/live/useLiveNodes";
import { useWaits } from "../agents/live/useWaits";
import { usePanels } from "../fleet/pstore";
import { findAgent, fleet, sessionTitle, useFleet, useNow } from "../fleet/store";
import { useLive } from "../shared/liveFeed";
import { Asks } from "./Asks";
import { agoWords, elapsedWords, glance, spendOf, STALE_MS, startGlance, useGlance } from "./data";

function Status() {
  const heard = useGlance((s) => s.heard);
  const feed = useGlance((s) => s.feed);
  const rekeyed = useGlance((s) => s.rekeyed);
  const now = useNow(true, 1000);
  const state = rekeyed ? "rekeyed" : !heard ? "connecting" : now - heard > STALE_MS ? "stale" : "live";
  const again = "open the glance again from Studio (Session's ... menu -> Open the glance)"; // 3.4.1.1 (63)
  const words = rekeyed === "restarted" ? `Studio was restarted and has a new key: ${again}`
    : rekeyed ? `Studio does not take this address's key: ${again}`
    : state === "connecting" ? "connecting to Studio..." : state === "stale"
    ? `stale: last heard ${agoWords(heard / 1000, now)}, reconnecting` : feed === "open" ? "live" : "live figures; the feed is reconnecting";
  return <span className="gz-status mono" data-testid="glance-status" data-state={state} data-stale={state === "stale" ? "1" : "0"} data-feed={feed}>{words}</span>;
}

function Now({ sid, sentence }: { sid: string; sentence: string }) {
  const harnesses = useFleet((s) => s.harnesses);
  const caps = useGlance((s) => s.caps);
  const now = useNow(true, 1000);
  const row = harnesses.find((h) => h.local)?.sessions.find((s) => s.session_id === sid);
  const sp = spendOf(harnesses, caps, sid);
  const pct = sp.pct === null ? null : Math.round(sp.pct * 100);
  return (
    <section className="gz-block gz-now" data-testid="glance-now" data-session={sid || undefined}>
      {row && <div className="gz-session mono muted" title={sessionTitle(row)}>{sessionTitle(row)}</div>}
      <p className="gz-narr" data-testid="glance-narration">{sentence}</p>
      <dl className="gz-facts">
        <div className="gz-fact" data-testid="glance-elapsed">
          <dt>Elapsed</dt>
          <dd>{row ? elapsedWords(row.started, now) || "not known" : "no session"}</dd>
        </div>
        <div className="gz-fact" data-testid="glance-spend" data-reached={sp.reached || undefined} data-spent={sp.spent}>
          <dt>Spend today</dt>
          <dd>
            {sp.spent} <span className="muted">· {sp.cap}</span>
            {sp.reached && <span className="gz-bad"> · reached: its sessions are paused</span>}
          </dd>
          {pct !== null && <div className="gz-bar" title={`${pct} % of the cap`}><span style={{ width: `${pct}%` }} /></div>}
        </div>
      </dl>
    </section>
  );
}

function Recent({ sid }: { sid: string }) {
  const lines = useLive((s) => s.lines);
  const now = useNow(true, 5000);
  const mine = lines.filter((l) => (!sid || l.key.split("|")[1] === sid) && l.kind !== "thinking" && (l.text || l.tool)).slice(-3).reverse();
  return (
    <section className="gz-block" data-testid="glance-recent" aria-label="The three most recent events">
      <h2 className="gz-h mono">LAST THREE</h2>
      {!mine.length ? (
        <p className="muted">Nothing has happened in this session since the page opened.</p>
      ) : (
        <ul className="gz-events">
          {mine.map((l) => {
            const who = findAgent(fleet.get(), l.key)?.a.name || l.key.split("|")[2] || "main";
            const what = l.kind === "tool" ? `ran ${l.tool}${l.target ? ": " + l.target : ""}` : l.text.split("\n")[0];
            return (
              <li key={l.n} className="gz-event" data-testid="glance-event" data-kind={l.kind} title={`${who}: ${what}`}>
                <span className="gz-ev-who mono">{who}</span>
                <span className="gz-ev-what">{what}</span>
                <span className="gz-ev-at mono muted">{agoWords(l.ts, now)}</span>
              </li>
            );
          })}
        </ul>
      )}
    </section>
  );
}

export function Glance() {
  const theme = useStore(studio, (s) => s.theme);
  const loaded = useFleet((s) => s.loaded);
  const { nodes, sid, now } = useLiveNodes("here");
  const { waits, path } = useWaits(nodes, now, true);
  const said = narrate(nodes, waits, path, (n) => n.group?.title || "").head; // the sentence; the spend is said below, honestly
  const rows = usePanels((s) => s.attention); // the array itself: a filtered copy per read would never settle
  const waiting = rows.filter((r) => !sid || r.session_id === sid);
  const asked = waiting.length ? `waiting on you: ${waiting[0].what}${waiting.length > 1 ? ` (and ${waiting.length - 1} more)` : ""}` : "";
  const sentence = said || asked || (sid ? "Nothing runs in this session right now." : loaded ? "Nothing runs on this machine right now." : "reading this machine's sessions...");
  useEffect(() => paint(theme), [theme]);
  useEffect(() => {
    document.title = "Glance - Halo Studio";
    startGlance();
    startAlerts((row) => glance.update(() => ({ lit: row.id })));
  }, []);
  return (
    <div className="gz" data-testid="glance">
      <div className="gz-col">
        <header className="gz-top">
          <span className="gz-brand mono">HALO · GLANCE</span>
          <Status />
        </header>
        <Now sid={sid} sentence={sentence} />
        <Asks />
        <Recent sid={sid} />
        <footer className="gz-foot muted">
          <a href="/?mode=session" data-testid="glance-studio">Open Studio</a>
          <span> · this page reads and answers through this Studio; it calls no model</span>
          {!ownerPage() && <p className="gz-bad" data-testid="glance-owner-note">This tab can look but not answer: Studio lets only a page you opened yourself answer. Paste the glance's address into the address bar (or run halo studio --mode glance).</p>}
        </footer>
      </div>
      <Toasts />
    </div>
  );
}
