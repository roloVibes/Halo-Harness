// session-prompt (3.3.11.0 R1, the owner: "a box to just type into like it is the tui but it's in session
// view, and you can open it if you want like how the cost and map modules work. I love looking at live, but
// that's more for steering"): type into the chosen session from Studio and know what became of it. The
// conversation the way the terminal shows it on top (PromptFeed.tsx), the box at the foot (PromptComposer.tsx).
// A strip at the foot of Session by default (the "+" menu and the palette bring it up, Alt+Enter too, and
// `halo studio --session <id> --prompt`); what it sends goes over the session's control socket with a receipt
// (promptStore.ts, promptSend.ts). The header names the session in words and says when a turn is running
// (PromptHead.tsx: 3.6.0.2 P27-P29, P31).
// 3.3.11.0 R2: a session with no terminal says so in the header, with Open in terminal and End session; with
// no session here the panel offers New session (NewSession.tsx).
// 3.6.0.2 P32: the picked session ended, nothing follows it and the box holds text: the header still names it, its
// feed stays, and the box is read-only with the ended line and Copy (PromptEnded.tsx) until another session is picked.
import { useEffect, useMemo } from "react";
import type { MotionState } from "../../lib/motion";
import { Metric } from "../orchestra/bits";
import { short } from "../orchestra/format";
import { localId, useFleet } from "../fleet/store";
import { loadReceipts, startPrompt, usePrompt } from "./promptStore";
import { NewSession } from "./NewSession";
import { PromptComposer } from "./PromptComposer";
import { PromptFeed } from "./PromptFeed";
import { PromptHead } from "./PromptHead";
import { lastRow } from "./pick";
import type { SessionRow } from "../fleet/types";
import { chosenSession, localSessions, useSession } from "./store";

const POLL_MS = 4000;
const NONE: SessionRow[] = []; // one empty list: a selector that made a new one each read would never settle

export function PromptDetail() {
  useEffect(() => startPrompt(), []);
  const ss = useFleet(chosenSession);
  const rows = useFleet((s) => (localSessions(s).length ? localSessions(s) : NONE));
  const hid = useFleet((s) => localId(s));
  const chosen = useSession((x) => x.chosen);
  const pick = useFleet((s) => s.scope.session || "") || chosen;
  const draft = usePrompt((s) => s.draft);
  const sid = ss?.session_id || "";
  useEffect(() => {
    if (!sid) return;
    void loadReceipts(sid);
    const t = window.setInterval(() => void loadReceipts(sid), POLL_MS);
    return () => window.clearInterval(t);
  }, [sid]);
  const gone = !ss && pick ? lastRow(pick)?.row || null : null; // R4 T8: the picked session that ended
  const ended = !!gone && !!draft.trim();
  const busy = !!ss && (ss.busy || ss.status === "busy" || ss.status === "waiting");
  const state = !ss ? "" : busy ? (ss.status === "waiting" ? "waits on you" : "a turn is running") : "idle";
  const off = !ss && !ended ? "No session here yet: New session above, or run halo in a terminal." : "";
  const feed = sid || gone?.session_id || "";
  return (
    <div className="spp" data-testid="prompt-detail" data-session={sid || undefined} data-busy={busy || undefined} data-ended={ended || undefined}>
      <PromptHead row={ss || gone} pick={ss ? sid : pick} rows={rows} state={state} />
      <div className="spp-body">{feed ? <PromptFeed sid={feed} hid={hid} /> : <NewSession compact />}</div>
      <footer className="spp-foot">
        <PromptComposer sid={sid} off={off} ended={ended} />
      </footer>
    </div>
  );
}

export function PromptGlance() {
  const ss = useFleet(chosenSession);
  const sid = ss?.session_id || "";
  const turns = usePrompt((s) => s.turns);
  const mine = useMemo(() => turns.filter((t) => t.sid === sid), [turns, sid]);
  const last = mine[mine.length - 1];
  return (
    <div className="glance" data-testid="prompt-glance">
      <div className="glance-numbers">
        <Metric value={mine.filter((t) => t.via === "studio").length} label="sent from here" />
      </div>
      <div className="glance-hint">{last ? short(last.text, 90) : "Type into this session as in the terminal: Alt+Enter."}</div>
    </div>
  );
}

export function usePromptMotion(): MotionState {
  const ss = useFleet(chosenSession);
  if (!ss) return "none";
  if (ss.status === "waiting") return "waiting";
  return ss.busy || ss.status === "busy" ? "working" : "idle";
}
