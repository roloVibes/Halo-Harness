// Agents -> 4 · Live (3.6.0.2 R52, section 4: "what a session is doing now, drawn on the map it really follows"). This is
// its SHELL (P4 batch 1): the view bar (the four-tab switch, then Attention, as every tab), a workspace `agents-live` with
// one main panel titled WORDS.live, and in it the session Session draws (routes/session/store.ts chosenSession) said in
// truth.ts's sentences -- its T-state line, its status line -- over a frame reserved for the drawing. No picker, no
// drawing and no fetch yet (P4 batch 3 draws the run in the frame; batch 4 the Feed beside it).
import { useEffect } from "react";
import { Workspace } from "../../lib/workspace/Workspace";
import type { PanelSpec } from "../../lib/workspace/types";
import { useStore } from "../../lib/store";
import { useSessionRecord } from "../../lib/work/record";
import { useFleet } from "../fleet/store";
import { lit, startLit } from "../crew/map/litStore";
import { statusLine, truthLines, truthState, WORDS, type TruthFacts } from "../crew/map/truth";
import { factsOf, knownNext, lastRow } from "../session/pick";
import { statusOf } from "../session/statusOf";
import { chosenSession } from "../session/store";
import { AttentionChip } from "./AttentionChip";
import { ViewSwitch } from "./ViewSwitch";

export const LIVE_SECTION = "agents-live";

/** No session row: the Start view's Empty ({B} as this page last heard it). */
const noneFacts = (b: string | null): TruthFacts => ({ none: true, title: "", a: null, plain: false, b, bSince: null, started: 0,
  turns: 0, studio: false, ended: null, machine: null, unreadable: null, changed: null, workflow: null, busy: false });

function LiveMain() {
  useEffect(() => startLit(), []);
  const row = useFleet(chosenSession);
  const pick = useFleet((s) => s.scope.session || "");
  const ended = !row && pick ? lastRow(pick) : null; // R4: one that ended reads T8 until another is picked
  const sid = row?.session_id || (ended ? pick : "");
  const f: TruthFacts = row ? factsOf(row) : ended ? factsOf(ended.row, ended.ended) : noneFacts(knownNext()?.b ?? null);
  const rec = useSessionRecord(sid);
  const rows = (rec?.agents || []).map((a) => ({ ...a.row, agent_id: a.id }));
  const events = useStore(lit, (x) => (sid ? x.events[sid] : undefined)) || [];
  const st = truthState(f);
  return (
    <div className="ag-live" data-testid="agents-live" data-sid={sid} data-map={f.a || ""}>
      <div className="cw-line mp-truth-said" data-testid="live-truth" data-state={st}>
        {truthLines(f).map((l, i) => <p key={i} className="mp-truth-line">{l.text}</p>)}
      </div>
      <p className="mp-status mono" data-testid="live-status">
        {sid && st !== "T8" ? statusLine(statusOf(rows, events, !!f.busy)) : ""}
      </p>
      <div className="ag-live-frame" data-testid="live-frame" />
    </div>
  );
}

export const livePanels: PanelSpec[] = [
  { id: "live-main", testid: "agents-live-panel", title: WORDS.live, role: "main",
    about: "What a session is doing now, drawn on the map it really follows.",
    help: "The session Session shows: which map it runs on, and what its agents do now.",
    face: "detail", glance: LiveMain, detail: LiveMain },
];

export function LiveView() {
  const lead = (
    <span className="cw-lead">
      <ViewSwitch view="live" />
      <AttentionChip />
    </span>
  );
  return (
    <div className="cw" data-testid="live-view">
      <Workspace section={LIVE_SECTION} specs={livePanels} lead={lead} />
    </div>
  );
}
