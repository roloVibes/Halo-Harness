// History under the map (3.6.0.0 R4; mapRuns.ts says what it reads): a picker of finished runs, newest first; Replay
// it on the map (the run lights the map it ran on, in quiet colours, as the scrubber moves); its report card opens from
// the picker row. The scrubber is Live's own (crew/live/Scrubber.tsx: drag, Play at 1x / 4x / 16x, Now). 3.6.0.0 R4b:
// "Goal runs, files, Compare" opens Live's whole History in the drawer (goal runs and saved files beside sessions).
import { useEffect } from "react";
import { Button } from "../../../lib/ui";
import { cost as money } from "../../orchestra/format";
import { ReportCard } from "../live/ReportCard";
import { Scrubber } from "../live/Scrubber";
import { closeRun, loadMapHistory, pickRun, replayRun, toggleCard, useMapHist } from "./mapRuns";
import { useLitNow } from "./useLit";
import { toggleHistory } from "../../agents/live/historyStore";
import { openFeed } from "./feedOpen";

const when = (t: number) => (t ? new Date(t * 1000).toLocaleString([], { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" }) : "");

export function MapHistory() {
  const L = useLitNow();
  const rows = useMapHist((s) => s.rows);
  const loaded = useMapHist((s) => s.loaded);
  const pick = useMapHist((s) => s.pick);
  const open = useMapHist((s) => s.open);
  const card = useMapHist((s) => s.card);
  const busy = useMapHist((s) => s.busy);
  const runningKey = L.all.map((s) => s.sid).join(",");
  useEffect(() => void loadMapHistory(new Set(runningKey ? runningKey.split(",") : [])), [runningKey]);
  const row = rows.find((r) => r.sid === pick);
  return (
    <section className="mp-history" data-testid="map-history" aria-label="History: past runs replayed on the map">
      <div className="mp-history-bar">
        <b>History</b>
        {!rows.length ? <span className="cw-line" data-testid="map-history-none">{loaded ? "No finished run yet." : "Reading the past runs..."}</span> : (
          <>
            <select className="input mp-history-pick" value={pick} onChange={(e) => pickRun(e.target.value)} data-testid="map-history-pick" aria-label="A finished run, newest first">
              {rows.map((r) => <option key={r.sid} value={r.sid}>{when(r.when)} · {r.what.slice(0, 60)}{r.cost !== null ? ` · ${money(r.cost)}` : ""}</option>)}
            </select>
            <Button variant="primary" disabled={!pick || busy} onClick={() => void replayRun()} data-testid="map-history-replay"
                    title="Replay it on the map it ran on, in quiet colours; the scrubber moves it">Replay it on the map</Button>
            <Button disabled={!pick} onClick={toggleCard} aria-pressed={!!card} data-testid="map-history-card" title="Its report card, from the record (no model call)">
              {card ? "Hide the report card" : "Report card"}
            </Button>
            {open && <Button onClick={closeRun} data-testid="map-history-now">Back to now</Button>}
          </>
        )}
        <Button onClick={() => (toggleHistory(true), openFeed("history"))} data-testid="map-history-all"
                title="Every past session, goal run and saved replay file, as Live's History lists them; tick two to compare">Goal runs, files, Compare</Button>
      </div>
      {open && L.mode === "replay" && <Scrubber sid={open.sid} title={open.title} started={null} lineup="" />}
      {card && row && <ReportCard refId={`session:${card}`} />}
    </section>
  );
}
