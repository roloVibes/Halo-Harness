// Agents -> 4 · Live's head (3.6.0.2 R34 R23 R28): the session's T-state from truth.ts (section 4's words, letter for
// letter), then its status line in a box two lines tall from the first draw. Both are read from the session's row at
// once: nothing here waits on the network. The status line says nothing for a session that ended (T8), one on another
// machine (T9, its agents are that machine's), one with no message yet (T10) or no session (Empty). Empty's [New session]
// opens the New session form (R5: only that form starts a session), on Session's Start view.
import { goSection, useStore } from "../../lib/store";
import { useSessionRecord } from "../../lib/work/record";
import { lit } from "../crew/map/litStore";
import { statusLine, truthLines, truthState, type TruthFacts } from "../crew/map/truth";
import { statusOf } from "../session/statusOf";

const QUIET = new Set(["T8", "T9", "T10", "Empty"]);

function newSession(): void {
  goSection("session");
  requestAnimationFrame(() => document.querySelector<HTMLElement>("[data-testid=session-start] [data-testid=session-new-cwd]")?.focus());
}

/** `off`: the hand-offs outside the map the drawing counted (R17), for the status line. */
export function LiveHead({ f, sid, off = 0 }: { f: TruthFacts; sid: string; off?: number }) {
  const st = truthState(f);
  const say = !!sid && !QUIET.has(st);
  const rec = useSessionRecord(say ? sid : "");
  const rows = (rec?.agents || []).map((a) => ({ ...a.row, agent_id: a.id }));
  const events = useStore(lit, (x) => (say ? x.events[sid] : undefined)) || [];
  return (
    <>
      <div className="cw-line mp-truth-said" data-testid="live-truth" data-state={st}>
        {truthLines(f).map((l, i) => (
          <p key={i} className="mp-truth-line">
            {l.text}
            {l.act === "new-session" && <>{" "}<button type="button" className="mp-link mp-truth-new" data-testid="live-truth-new" onClick={newSession}>{l.label}</button></>}
          </p>
        ))}
      </div>
      <p className="mp-status mono" data-testid="live-status">{say ? statusLine(statusOf(rows, events, !!f.busy, off)) : ""}</p>
    </>
  );
}
