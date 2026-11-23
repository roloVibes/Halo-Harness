// The Live column's foot (3.1.7.0 R1): the Steer box. 3.6.0.11 (the owner:
// "Keep it off as default, open it with the steer button, and add the ability
// to close it"): it is there only while open (Live.tsx, steer.ts openSteer),
// and x or Esc in the field closes it (closeSteer). It talks to the pinned agent, or, with none
// pinned, to the chosen session's main agent; its header says who ("STEER
// main", "STEER researcher") in that agent's colour, and Pause and Stop sit
// beside it for that same agent (Stop asks first: the Fleet confirm dialog).
// When that agent has finished the box is disabled and says so in one line.
// A steer sent here echoes in the column as a YOU line at once
// (shared/liveTree.ts) and lands in the agent's next step.
// 3.3.0.0 R6: above the field the target line names the agent and what it
// does now (LiveTarget.tsx); while the field has the keyboard the column does
// not move (steer.ts setComposing); Tab / Shift+Tab in the field cycle the
// target among the session's live agents; Escape closes the box and follows
// again (3.6.0.11). The field keeps its text when the target changes.
// 3.3.5.0 R4: a request larger than its local window shows its preflight line
// and three buttons (LivePreflight.tsx); 3.6.0.11: it and the eyes offer sit in the foot, open box or not.
// 3.3.6.0 R6: Ctrl+V with an image, or a file dropped on the box, becomes the chip under it (LiveImage.tsx,
// steerImage.ts); Send then posts the steer with its image to the session, the offer's choice with it.
import { useEffect, type ClipboardEvent, type DragEvent, type FocusEvent, type KeyboardEvent } from "react";
import { Button, Icon } from "../../lib/ui";
import { askStop, togglePause } from "../fleet/actions";
import { pauseSet } from "../fleet/pauseFact";
import { endedAt } from "../crew/map/truth";
import { Steer } from "../fleet/Steer";
import { hueOf } from "../shared/hues";
import { useFleet } from "../fleet/store";
import { LiveImage } from "./LiveImage"; // 3.3.6.0 R6: the steer's image
import { imageFile, sendWithImage, steerImage, takeFile } from "./steerImage";
import { chosenSession } from "./store";
import { noteSteerDraft, steerText } from "./pick";
import { TargetLine } from "./LiveTarget";
import { closeSteer, cycleTarget, setComposing, targetName, useSteerTarget } from "./steer";

const inField = (e: { target: EventTarget }) => (e.target as HTMLElement).dataset?.testid === "fleet-steer";

function onKeys(e: KeyboardEvent<HTMLDivElement>): void {
  if (!inField(e) || e.ctrlKey || e.metaKey || e.altKey) return;
  if (e.key === "Tab") {
    if (cycleTarget(e.shiftKey ? -1 : 1)) e.preventDefault(); // with no other live agent Tab moves the focus on, as usual
  } else if (e.key === "Escape") closeSteer(); // 3.6.0.11: Esc closes the box (and follows again); its text is kept
}
const onFocus = (e: FocusEvent<HTMLDivElement>) => inField(e) && setComposing(true);
const onBlur = (e: FocusEvent<HTMLDivElement>) => inField(e) && setComposing(false);

const FINISHED = ["done", "failed", "stopped"];
const CLOSE = "Close the steer box (Esc)";
// the text typed and not sent (pick.ts steerText): it survives a close and is there on the next open; a send clears it

export function LiveSteer() {
  const t = useSteerTarget();
  const ss = useFleet(chosenSession);
  const hid = useFleet((s) => s.scope.harness || "local");
  const ended = useFleet((s) => (s.ended?.key === t.key && s.ended.door === "feed" ? s.ended.t : 0)); // Stop confirmed after it ended
  const take = (e: ClipboardEvent<HTMLDivElement> | DragEvent<HTMLDivElement>, from: "paste" | "drop") => {
    const f = imageFile("clipboardData" in e ? e.clipboardData : e.dataTransfer);
    if (!f || !ss) return;
    e.preventDefault();
    void takeFile(f, ss.session_id, ss.model, from);
  };
  const send = (text: string) => (steerImage.get().img && ss ? sendWithImage(hid, ss.session_id, text) : null);
  const over = (e: DragEvent<HTMLDivElement>) => {
    if (e.dataTransfer?.types?.includes("Files")) e.preventDefault();
  };
  const off = !t.key || !t.ref || FINISHED.includes(String(t.ref.a.state)) || t.ref.h.allow_control === "none";
  useEffect(() => void (off && setComposing(false)), [off]); // a field that goes away (or is disabled) holds no keyboard
  if (!t.key)
    return <div className="slv-hint mono muted" data-testid="session-live-hint">No session here yet: start one in a terminal (halo) and steer it from here.</div>;
  const a = t.ref?.a;
  const name = targetName(t);
  const noControl = t.ref?.h.allow_control === "none";
  const done = !a || FINISHED.includes(String(a.state));
  const why = !a
    ? `${name} is not in this session any more: pin a live agent to steer`
    : noControl
      ? `${t.ref?.h.name || "that harness"} takes no commands from here (allow_control none)`
      : done
        ? `${name} has finished (${a.state}): pin a live agent to steer`
        : undefined;
  const paused = !!a && pauseSet(a); // F3: a pause set and not yet taken back reads Resume, also before it holds
  const head = (
    <span className="slv-steer-to" title={a ? `${a.name || a.agent_id}: ${a.state}${t.main ? " (the session's main agent)" : ""}` : undefined}>
      <span className="rail-label mono">STEER</span>
      <span className="mono slv-steer-name" data-testid="session-live-steer-to">{name}</span>
    </span>
  );
  const extra = (
    <>
      <Button size="sm" icon={<Icon name={paused ? "play" : "pause"} />} disabled={!!why} onClick={() => void togglePause(t.key)} data-testid="session-live-pause"
              title={why || (paused ? `Resume ${name}` : `Pause ${name} at its next step`)}>
        {paused ? "Resume" : "Pause"}
      </Button>
      <Button size="sm" variant="danger" icon={<Icon name="stop" />} disabled={!!why} onClick={() => askStop(t.key, "feed")} data-testid="session-live-stop"
              title={why || `Stop ${name} at its next step (asks first)`}>
        Stop
      </Button>
      {ended ? <span className="slv-ended mono muted" data-testid="session-live-stop-ended">{endedAt(ended)}</span> : null}
      <Button size="sm" variant="ghost" icon={<Icon name="close" />} onClick={closeSteer} data-testid="session-live-steer-close" aria-label={CLOSE} title={CLOSE} />
    </>
  );
  return (
    <div className="slv-steer holo-frame" data-testid="session-live-steer" data-key={t.key} data-hc={hueOf(t.key)} data-main={t.main || undefined} data-disabled={!!why || undefined}
         onKeyDown={onKeys} onFocus={onFocus} onBlur={onBlur} onPaste={(e) => take(e, "paste")} onDrop={(e) => take(e, "drop")}
         onDragOver={over}>
      <TargetLine t={t} name={name} />
      <Steer k={t.key} where="live" disabled={!!why} why={why} head={head} extra={extra} send={send} initial={steerText()} onText={noteSteerDraft} />
      <LiveImage />
    </div>
  );
}
