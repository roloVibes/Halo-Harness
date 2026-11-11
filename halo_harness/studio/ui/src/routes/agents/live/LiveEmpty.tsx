// What Live says when nothing runs, and the banner over a replay (3.3.18.0 "The living canvas"). Empty: one sentence and
// two plain actions -- Open the plan (Cast) and Replay the last session (History's newest session, as a replay). The
// banner runs across the canvas while a replay is open: "replay -- ended <when>", what it was, and Back to now.
import { Button } from "../../../lib/ui";
import { setAgentsView } from "../store";
import { ago, closeHistory } from "./History";
import { useHistory } from "./historyStore";
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
    </div>
  );
}

export function ReplayBanner() {
  const r = useLiveReplay();
  if (!r) return null;
  const back = () => (backToNow(), closeHistory());
  return (
    <div className="lv-replay mono" role="status" data-testid="live-replay-banner" data-kind={r.kind} data-id={r.id}>
      <b className="lv-replay-word">replay</b>
      <span className="lv-replay-when">ended {ago(r.ended)}</span>
      <span className="lv-replay-what" title={r.title}>{r.title}</span>
      <span className="spacer" />
      <Button size="sm" onClick={back} data-testid="live-replay-back" title="Leave the replay: the canvas shows what runs now">Back to now</Button>
    </div>
  );
}
