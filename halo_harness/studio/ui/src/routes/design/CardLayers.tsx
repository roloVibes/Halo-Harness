// What draws over an artboard's frame (3.0.7.0 R3b): the comment layer (with
// the Comment tool on, a click anywhere on the frame opens a small comment
// box at that point), the numbered pins of its open comments (click one for
// its text and Resolve), the comment box itself, and the inline editor a
// double-click on a prototype's text opens (Save makes a new version, Esc
// cancels). Each part reads only its own artboard's slice of the store.
import { useEffect, useRef, useState, type KeyboardEvent, type MouseEvent } from "react";
import { Button } from "../../lib/ui";
import { cancelEdit, saveText } from "./edit";
import { pinComment, resolveComment } from "./more";
import { design, useDesign } from "./store";
import type { Comment } from "./types";

const pct = (v: number) => Math.round(Math.max(0, Math.min(100, v)) * 10) / 10;

/** Enter saves, Shift+Enter is a new line, Esc cancels. */
function keys(save: () => void, cancel: () => void) {
  return (e: KeyboardEvent) => {
    if (e.key === "Escape") (e.preventDefault(), e.stopPropagation(), cancel());
    else if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing) (e.preventDefault(), save());
  };
}

function CommentBox({ aid }: { aid: string }) {
  const at = useDesign((s) => (s.pinAt?.aid === aid ? s.pinAt : null));
  const busy = useDesign((s) => s.busy === "comment");
  const [text, setText] = useState("");
  const box = useRef<HTMLTextAreaElement>(null);
  useEffect(() => {
    setText("");
    if (at) box.current?.focus();
  }, [at]);
  if (!at) return null;
  const cancel = () => design.update(() => ({ pinAt: null }));
  const save = () => void pinComment(text);
  return (
    <form className="da-pop" style={{ left: `${at.x}%`, top: `${at.y}%` }} data-testid="design-comment" onSubmit={(e) => (e.preventDefault(), save())}
          onPointerDown={(e) => e.stopPropagation()} onClick={(e) => e.stopPropagation()}>
      <textarea ref={box} className="input" rows={3} value={text} onChange={(e) => setText(e.target.value)} onKeyDown={keys(save, cancel)}
                placeholder="What should change here?" aria-label="Comment text" data-testid="design-comment-text" />
      <div className="da-pop-row">
        <Button size="sm" variant="ghost" type="button" onClick={cancel}>Cancel</Button>
        <Button size="sm" variant="primary" type="submit" disabled={!text.trim() || busy} data-testid="design-comment-save">Pin comment</Button>
      </div>
    </form>
  );
}

function PinPop({ c, n }: { c: Comment; n: number }) {
  return (
    <div className="da-pop" style={{ left: `${c.x}%`, top: `${c.y}%` }} data-testid="design-pin-pop" onPointerDown={(e) => e.stopPropagation()} onClick={(e) => e.stopPropagation()}>
      <div className="da-pop-head mono muted">
        #{n}{c.source === "critique" ? " · critique" : ""} · on v{c.version}
        <span className="spacer" />
        <button className="icon-btn" aria-label="Close" onClick={() => design.update(() => ({ pinOpen: "" }))}>x</button>
      </div>
      <p className="da-pop-text">{c.text}</p>
      <div className="da-pop-row">
        <Button size="sm" variant="primary" onClick={() => void resolveComment(c.id)} data-testid="design-resolve">Resolve</Button>
      </div>
    </div>
  );
}

function TextEditor({ aid, scale }: { aid: string; scale: number }) {
  const e = useDesign((s) => (s.editing?.aid === aid ? s.editing : null));
  const busy = useDesign((s) => s.busy === "text");
  const [text, setText] = useState("");
  const box = useRef<HTMLTextAreaElement>(null);
  useEffect(() => {
    setText(e ? e.text.trim() : "");
    if (e) window.setTimeout(() => (box.current?.focus(), box.current?.select()), 0);
  }, [e]);
  if (!e) return null;
  const save = () => void saveText(text);
  return (
    <form className="da-pop da-edit" style={{ left: e.x * scale, top: e.y * scale, minWidth: Math.max(200, e.w * scale) }} data-testid="design-text-edit"
          onSubmit={(ev) => (ev.preventDefault(), save())} onPointerDown={(ev) => ev.stopPropagation()}>
      <div className="da-pop-head mono muted">edit {e.tag} text</div>
      <textarea ref={box} className="input" rows={Math.min(5, Math.max(1, Math.ceil(text.length / 34)))} value={text} onChange={(ev) => setText(ev.target.value)}
                onKeyDown={keys(save, cancelEdit)} aria-label="The text" data-testid="design-text-edit-input" />
      <div className="da-pop-row">
        <span className="mono muted">Enter saves · Esc cancels</span>
        <span className="spacer" />
        <Button size="sm" variant="ghost" type="button" onClick={cancelEdit}>Cancel</Button>
        <Button size="sm" variant="primary" type="submit" disabled={busy} data-testid="design-text-edit-save">Save</Button>
      </div>
    </form>
  );
}

/** The layers over one card's frame; `scale` is the prototype's scale on the card (text boxes are in its pixels). */
export function CardLayers({ aid, pins, scale }: { aid: string; pins: Comment[]; scale: number }) {
  const commenting = useDesign((s) => s.tool === "comment");
  const open = useDesign((s) => (pins.some((c) => c.id === s.pinOpen) ? s.pinOpen : ""));
  const place = (ev: MouseEvent<HTMLDivElement>) => {
    const r = ev.currentTarget.getBoundingClientRect();
    if (!r.width || !r.height) return;
    design.update(() => ({ pinAt: { aid, x: pct(((ev.clientX - r.left) / r.width) * 100), y: pct(((ev.clientY - r.top) / r.height) * 100) }, pinOpen: "", sel: aid }));
  };
  return (
    <>
      {commenting && <div className="da-overlay" onClick={place} title="Click to pin a comment here" data-testid="design-comment-layer" />}
      {pins.map((c, i) => (
        <button key={c.id} className="da-pin" data-crit={c.source === "critique" || undefined} style={{ left: `${c.x}%`, top: `${c.y}%` }} data-testid="design-pin"
                title={c.text} aria-label={`Comment ${i + 1}: ${c.text}`} aria-expanded={open === c.id}
                onPointerDown={(e) => e.stopPropagation()} onClick={(e) => (e.stopPropagation(), design.update((s) => ({ pinOpen: s.pinOpen === c.id ? "" : c.id, pinAt: null })))}>
          {i + 1}
        </button>
      ))}
      {open && <PinPop c={pins.find((c) => c.id === open)!} n={pins.findIndex((c) => c.id === open) + 1} />}
      <CommentBox aid={aid} />
      <TextEditor aid={aid} scale={scale} />
    </>
  );
}
