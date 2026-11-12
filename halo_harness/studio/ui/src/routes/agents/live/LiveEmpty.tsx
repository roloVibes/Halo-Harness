// What Live says when nothing runs, and the banner over a replay (3.3.18.0 "The living canvas"). Empty: one sentence and
// two plain actions -- Open the plan (Cast) and Replay the last session (History's newest session, as a replay). The
// banner runs across the canvas while a replay is open: "replay -- <the moment drawn>" (3.4.1.0 R1: the scrubber's), when it
// ended (or that it runs now), what it was, and Back to now. 3.4.1.0 R3: under the actions, a ROW for the session that
// ended last -- what it was, when it ended, and its Report card (a page of History; never a pop-up, nothing opens by itself).
import { Button } from "../../../lib/ui";
import { setAgentsView } from "../store";
import { ago, closeHistory } from "./History";
import { openCard, useHistory } from "./historyStore";
import { backToNow, openLiveReplay, useLiveReplay } from "./replay";

export const EMPTY_LINE = "Nothing is running. Start a session, or open the last one as a replay.";

/** `compact`: a strip over the fleet's machines (they are here even when nothing runs on them). */
export function LiveEmpty({ compact = false }: { compact?: boolean }) {
  const last = useHistory((s) => s.rows.find((r) => r.kind === "session"));
  const loaded = useHistory((s) => s.loaded);
  return (
    <div className={"empty lv-empty" + (compact ? " lv-empty-strip" : "")} data-testid="roles-live-empty">
      <div className="empty-title" data-testid="live-empty-line">{EMPTY_LINE}</div>
      <div className="empty-action lv-empty-acts">
        <Button size="sm" onClick={() => setAgentsView("cast")} data-testid="live-empty-plan" title="Agents -> Cast: the lineup new sessions use, its cards and tiers">
          Open the plan (Cast)
        </Button>
        <Button size="sm" disabled={!last} onClick={() => last && void openLiveReplay("session", last.id, last.what)} data-testid="live-empty-replay"
                title={last ? `Draw "${last.what}" (${ago(last.when)}) as it ended, muted, under a replay banner` : loaded ? "No past session on this harness yet" : "reading the past..."}>
          Replay the last session
        </Button>
      </div>
      {last && (
        <button className="lv-ended mono" onClick={() => openCard(`session:${last.id}`, last.what)} data-testid="live-empty-card" data-id={last.id}
                title={`${last.what}
Its report card: the story, where the time and money went, what failed, what waited on you, the files (from the record, no model call)`}>
          <span className="lv-ended-what">ended {ago(last.when + (last.secs || 0))}: {last.what}</span>
          <span className="lv-ended-go">Report card</span>
        </button>
      )}
    </div>
  );
}

const KIND: Record<string, string> = { session: "", run: "goal run", mission: "mission", file: "file" };

export function ReplayBanner() {
  const r = useLiveReplay();
  if (!r) return null;
  const back = () => (backToNow(), closeHistory());
  const at = new Date(r.t * 1000).toLocaleTimeString(undefined, { hour: "2-digit", minute: "2-digit", second: "2-digit" });
  return (
    <div className="lv-replay mono" role="status" data-testid="live-replay-banner" data-kind={r.kind} data-id={r.id} data-at={Math.round(r.t - r.tl.t0)}>
      <b className="lv-replay-word">replay -- {at}</b>
      <span className="lv-replay-when">{[KIND[r.kind], r.live ? "running now" : `ended ${ago(r.ended)}`].filter(Boolean).join(" · ")}</span>
      <span className="lv-replay-what" title={r.title}>{r.title}</span>
      <span className="spacer" />
      <Button size="sm" onClick={back} data-testid="live-replay-back" title="Leave the replay: the canvas shows what runs now">Back to now</Button>
    </div>
  );
}
