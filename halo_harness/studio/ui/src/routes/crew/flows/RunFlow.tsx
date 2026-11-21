// Run it (3.6.0.6 P): the ONE control that starts a real run of a crew workflow, offered the same way in every view
// that shows one. A press opens its form in place, under the button (no pop-up, no navigation): the workflow's name,
// the task, the line that says what a run does and costs, Run and Cancel. Run answers with the receipt in the same
// room (its height is kept, so nothing under it moves) and Watch it in Live, which goes there only when pressed.
import { useEffect, useLayoutEffect, useRef, useState } from "react";
import { Button, TextBox } from "../../../lib/ui";
import { CANCEL, RUN, RUN_IT, WATCH, canRun, offer, runLine, startedLine, type RunRow } from "./runWords";
import { cancelRun, keyOf, loadFolder, openRun, setRunText, startRun, useRunForm, watchRun } from "./runFlowStore";

type Props = RunRow & { where: string };

/** The button alone (a view that draws its form elsewhere, e.g. beside Try it). None for a workflow a session does
 *  not run by name (one that ships with Halo: Copy makes it yours). */
export function RunItButton({ name, scope, problems, where }: Props) {
  const { show, off } = offer({ name, scope, problems });
  const open = useRunForm((s) => s.at === keyOf(where, name) && !s.sid); // after the receipt it opens a new form
  useEffect(() => { if (show) void loadFolder(); }, [show]);
  if (!show) return null;
  return (
    <Button disabled={!!off || open} title={off || undefined} onClick={() => void openRun(where, name)}
            data-testid="run-flow-open" data-name={name} data-where={where}>{RUN_IT}</Button>
  );
}

/** The form (or, once Run answered, the receipt) of this view's Run it; nothing while it is closed. */
export function RunItForm({ name, where }: { name: string; where: string }) {
  const s = useRunForm((x) => (x.at === keyOf(where, name) ? x : null));
  const room = useRef<HTMLDivElement | null>(null);
  const box = useRef<HTMLTextAreaElement | null>(null);
  const at = s?.at || "";
  useEffect(() => { if (at) box.current?.focus({ preventScroll: true }); }, [at]); // the task box takes the keys; nothing scrolls
  const [tall, setTall] = useState(0);
  useLayoutEffect(() => { // the form's height is kept for the receipt, so the views under it hold still
    if (s && !s.sid && room.current) setTall(room.current.offsetHeight);
  }, [s]);
  if (!s) return null;
  if (s.sid)
    return (
      <div className="rf-form" style={{ minHeight: tall || undefined }} data-testid="run-flow-started" aria-live="polite">
        <span className="cw-line" data-testid="run-flow-receipt">{startedLine(s.sid)}</span>
        <div className="cw-row"><Button variant="primary" onClick={watchRun} data-testid="run-flow-watch">{WATCH}</Button></div>
      </div>
    );
  return (
    <div className="rf-form" ref={room} data-testid="run-flow-form" data-name={name}>
      <b className="mono" data-testid="run-flow-name">{name}</b>
      <TextBox value={s.text} onChange={(e) => setRunText(e.target.value)} aria-label="The task" data-testid="run-flow-task" ref={box} />
      <span className="cw-line" data-testid="run-flow-line">{runLine(s.folder)}</span>
      <div className="cw-row">
        <Button variant="primary" disabled={!canRun(s.text, s.busy)} onClick={() => void startRun()} data-testid="run-flow-run">{RUN}</Button>
        <Button onClick={cancelRun} data-testid="run-flow-cancel">{CANCEL}</Button>
      </div>
      {s.error && <span className="cw-line" data-tone="bad" data-testid="run-flow-error">{s.error}</span>}
    </div>
  );
}

/** Run it with its form under it: every view but the Workflows tab's (which puts the button beside Try it). */
export function RunFlow(p: Props) {
  return (
    <div className="rf" data-testid="run-flow" data-name={p.name} data-where={p.where}>
      <RunItButton {...p} />
      <RunItForm name={p.name} where={p.where} />
    </div>
  );
}
