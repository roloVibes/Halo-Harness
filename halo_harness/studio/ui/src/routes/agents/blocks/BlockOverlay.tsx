// Over the Cast canvas and the Workflows board (3.3.16.3): the library on Cast (the same panel W shows), the one-line
// result of the last block change (its x dismisses it), the confirm card a drop raises before it writes (WHAT / COSTS /
// WRITES, then its button or Cancel), the keyboard move's hint, and the label under the pointer while a block drag moves.
// Nothing here opens on load.
import { Button } from "../../../lib/ui";
import { Library } from "../workflows/Library";
import { useDrag } from "./drag";
import { useMoving } from "./keyMove";
import { cancelAsk, confirmAsk, unsay, useBlockNote } from "./note";
import { useAgentsView } from "../store";

export function BlockNote() {
  const line = useBlockNote((s) => s.line);
  const tone = useBlockNote((s) => s.tone);
  if (!line) return null;
  return (
    <div className="blk-note mono" data-testid="blk-note" data-tone={tone} role="status">
      <span className="blk-note-text">{line}</span>
      <button className="icon-btn" onClick={unsay} aria-label="Dismiss this line" data-testid="blk-note-x">×</button>
    </div>
  );
}

export function BlockConfirm() {
  const a = useBlockNote((s) => s.ask);
  const busy = useBlockNote((s) => s.busy);
  if (!a) return null;
  const lines: [string, string][] = [["WHAT", a.what], ["COSTS", a.costs], ["WRITES", a.writes]];
  return (
    <div className="wf-confirm blk-confirm" role="group" aria-label={a.title} data-testid="blk-confirm" data-kind={a.kind}>
      <b className="wf-confirm-title">{a.title}</b>
      <dl className="wf-confirm-lines">
        {lines.map(([k, v]) => <div key={k}><dt className="mono">{k}</dt><dd data-line={k.toLowerCase()}>{v}</dd></div>)}
      </dl>
      <div className="wf-page-actions" data-density="bar">
        <Button variant="primary" size="sm" disabled={busy} onClick={() => void confirmAsk()} data-testid="blk-confirm-do">{busy ? "Writing..." : a.button}</Button>
        <Button size="sm" variant="ghost" onClick={cancelAsk} data-testid="blk-confirm-cancel">Cancel</Button>
      </div>
    </div>
  );
}

function MoveHint() {
  const m = useMoving();
  if (!m) return null;
  return (
    <div className="blk-move mono" data-testid="blk-move" role="status">
      Move {m.bio}{m.from ? ` from ${m.from}` : ""} into: <b data-testid="blk-move-target">{m.targets[m.at]?.label || "-"}</b> (arrows pick, Enter moves, Esc stops)
    </div>
  );
}

export function DragGhost() {
  const label = useDrag((s) => (s.payload ? s.label : ""));
  const x = useDrag((s) => s.x);
  const y = useDrag((s) => s.y);
  if (!label) return null;
  return <div className="blk-ghost mono" data-drag-ghost data-testid="blk-ghost" style={{ left: x + 14, top: y + 10 }}>{label}</div>;
}

/** On Cast's canvas: the library beside it, the line, the card, the hint. */
export function BlockOverlay() {
  if (useAgentsView() !== "cast") return null;
  return (
    <>
      <div className="blk-lib"><Library /></div>
      <BlockNote />
      <BlockConfirm />
      <MoveHint />
    </>
  );
}
