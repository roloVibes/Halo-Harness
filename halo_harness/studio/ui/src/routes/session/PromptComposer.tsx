// The Prompt panel's box (3.3.11.0 R1): it behaves like the terminal's prompt. Enter sends, Shift+Enter is a new
// line, Up / Down go to the start / end of the prompt first (a wrapped line: a screen line at a time; promptKeys.ts,
// the terminal's rule), then
// walk this session's history (kept in this browser);
// `/` opens the slash list (the TUI's own table and the session's custom commands: name, arguments, one line of
// help) filtered as you type, Up / Down move in it, Tab (or Enter on a name not yet complete) completes, Esc
// closes it. Ctrl+V with an image, or an image file dropped on the box, becomes the chip under it (the steer
// box's path, steerImage.ts); a dropped file path (text) lands in the text. While a turn runs the send is
// refused first and the busy line offers Queue it and Steer (promptSend.ts). 3.3.15.0 R3: the box is the one TextBox
// with `fill`: three lines at the least, it grows with the draft and takes the panel's free height while the feed is
// short; the keys moved from its placeholder into the panel's `?`. 3.4.1.3 ("Pick, don't type"): `/model ` opens THE
// model picker over the box (type to filter, Up / Down, Enter); a pick writes `/model <ref>` and Enter sends it.
import { useEffect, useMemo, useRef, useState, type ClipboardEvent, type DragEvent, type KeyboardEvent } from "react";
import { Button, Icon, TextBox } from "../../lib/ui";
import { history, setDraft } from "./promptDraft";
import { loadSlash, prompt, slashMatches, usePrompt } from "./promptStore";
import { ModelPicker } from "../shared/picker/ModelPicker";
import { resolveBusy, send } from "./promptSend";
import { editStart } from "./promptWords";
import { imageFile, kb, readImage } from "./steerImage";
import { PromptEnded } from "./PromptEnded";
import { afterNative, arrowMove, isWalking } from "./promptKeys";

const BARE_MODEL = /^\s*\/model\s*$/; // 3.6.0.2 P69: Enter on a bare `/model` opens the model picker

function droppedPath(dt: DataTransfer | null): string {
  const uri = (dt?.getData("text/uri-list") || "").split(/\r?\n/).find((x) => x && !x.startsWith("#")) || "";
  if (uri.startsWith("file://")) return decodeURIComponent(uri.replace(/^file:\/\/(localhost)?/, "").replace(/^\/([A-Za-z]:)/, "$1"));
  return (dt?.getData("text/plain") || uri).trim();
}

/** `ended`: 3.6.0.2 P32, the picked session ended with text in the box: read-only, the line and Copy over it. */
export function PromptComposer({ sid, off, ended = false }: { sid: string; off: string; ended?: boolean }) {
  const draft = usePrompt((s) => s.draft);
  const busy = usePrompt((s) => s.busy);
  const sending = usePrompt((s) => s.sending);
  const img = usePrompt((s) => s.img);
  const imgError = usePrompt((s) => s.imgError);
  const focus = usePrompt((s) => s.focus);
  const rows = usePrompt((s) => s.slash[sid]);
  const box = useRef<HTMLTextAreaElement>(null);
  const [pick, setPick] = useState(0);
  const [closed, setClosed] = useState("");
  const [hist, setHist] = useState(-1);
  const before = useRef(""); // the draft Up walked away from; Down past the newest entry brings it back (as the terminal)
  // 3.6.0.2 P72: the coming edit's kind and selection start (beforeinput; a composition from where it began)
  const editAt = useRef<{ type: string; at: number } | null>(null);
  const settle = useRef(0); // P3: the zero-delay look after the browser's own Up / Down; cleared when the box goes
  useEffect(() => () => window.clearTimeout(settle.current), []);
  useEffect(() => void loadSlash(sid), [sid]);
  useEffect(() => {
    const el = box.current;
    if (!el) return;
    let comp: number | null = null;
    const start = () => void (comp = el.selectionStart);
    const note = (e: Event) => {
      const type = (e as InputEvent).inputType || "";
      if (type !== "insertCompositionText") comp = null;
      editAt.current = { type, at: Math.min(el.selectionStart, comp ?? el.selectionStart) };
    };
    el.addEventListener("compositionstart", start);
    el.addEventListener("beforeinput", note);
    return () => (el.removeEventListener("compositionstart", start), el.removeEventListener("beforeinput", note));
  }, []);
  const edited = (value: string) => {
    const e = editAt.current; // unknown: 0, so a send in flight leaves the box alone
    setDraft(value, editStart(e?.type || "", e ? e.at : null, box.current?.selectionStart ?? 0));
    editAt.current = null;
  };
  useEffect(() => {
    if (!focus) return;
    const timers = [0, 60, 200, 500, 1000].map((ms) => window.setTimeout(() => {
      const el = box.current;
      if (el && document.activeElement !== el) el.focus({ preventScroll: true });
    }, ms));
    return () => timers.forEach((t) => window.clearTimeout(t));
  }, [focus]);
  const matches = useMemo(() => (closed === draft ? [] : slashMatches(rows, draft)), [rows, draft, closed]);
  const modelPick = /^\/model\s+$/.test(draft) && closed !== draft;
  const backToBox = () => window.setTimeout(() => box.current?.focus(), 0);
  const at = Math.min(pick, Math.max(0, matches.length - 1));
  const complete = () => {
    const row = matches[at];
    if (!row) return false;
    setDraft(`/${row.name} `);
    setPick(0);
    return true;
  };
  const go = () => {
    if (BARE_MODEL.test(draft)) return void (setClosed(""), setDraft("/model ")); // 3.6.0.2 P69: the picker, nothing sent
    setHist(-1);
    void send(sid, draft);
  };
  /** Up / Down (promptKeys.ts): in the box first, then the sent prompts; with nothing to recall, nothing moves. */
  const arrow = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    const el = e.currentTarget, h = history(sid);
    const move = arrowMove(e.key, el.value, el.selectionStart, el.selectionEnd, isWalking(el.value, el.selectionStart, el.selectionEnd, h[hist]));
    if (move === "native") return;
    if (move === "start" || move === "end") { // 3.6.0.17 P3: the browser's own move (a screen line), then judged
      const key = e.key, from = move === "start" ? el.selectionStart : el.selectionEnd;
      window.clearTimeout(settle.current);
      settle.current = window.setTimeout(() => {
        if (!el.isConnected) return;
        const to = afterNative(key, from, el.selectionStart, el.value.length);
        if (to !== null) el.setSelectionRange(to, to);
      }, 0);
      return;
    }
    e.preventDefault();
    const next = hist < 0 ? (move === "older" ? h.length - 1 : -1) : hist + (move === "older" ? -1 : 1);
    if (next < 0) return; // nothing older to recall, or Down with nothing recalled: nothing moves
    if (hist < 0) before.current = draft;
    setHist(next >= h.length ? -1 : next);
    setDraft(next >= h.length ? before.current : h[next]);
  };
  const onKey = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    const el = e.currentTarget;
    if (ended) return; // P32: read-only, nothing is sent or recalled
    if (matches.length && (e.key === "ArrowDown" || e.key === "ArrowUp")) {
      e.preventDefault();
      setPick((at + (e.key === "ArrowDown" ? 1 : matches.length - 1)) % matches.length);
    } else if (matches.length && e.key === "Tab" && !e.shiftKey) {
      if (complete()) e.preventDefault();
    } else if (e.key === "Escape") {
      if (matches.length) (e.preventDefault(), setClosed(draft));
      else el.blur();
    } else if (e.key === "Enter" && !e.shiftKey && !e.altKey) {
      e.preventDefault();
      const typed = draft.slice(1);
      if (!BARE_MODEL.test(draft) && matches.length && matches[at] && matches[at].name !== typed) complete();
      else go();
    } else if ((e.key === "ArrowUp" || e.key === "ArrowDown") && !e.shiftKey && !e.altKey && !e.metaKey && !e.ctrlKey) arrow(e);
  };
  const take = async (e: ClipboardEvent<HTMLDivElement> | DragEvent<HTMLDivElement>, from: "paste" | "drop") => {
    if (ended) return void e.preventDefault(); // P32: nothing lands in a read-only box
    const dt = "clipboardData" in e ? e.clipboardData : e.dataTransfer;
    const f = imageFile(dt);
    if (f) {
      e.preventDefault();
      const got = await readImage(f, from);
      prompt.update(() => (got.img ? { img: got.img, imgError: "" } : { imgError: got.error || "not an image" }));
    } else if (from === "drop") {
      const path = droppedPath(dt);
      if (!path) return;
      e.preventDefault();
      setDraft(draft + (draft && !/\s$/.test(draft) ? " " : "") + path, draft.length); // added at the end
    }
  };
  return (
    <div className="spp-composer" data-testid="prompt-composer" data-disabled={!!off || undefined} onPaste={(e) => void take(e, "paste")}
         onDrop={(e) => void take(e, "drop")} onDragOver={(e) => e.dataTransfer?.types?.length && e.preventDefault()}>
      {ended && <PromptEnded text={draft} />}
      {busy && busy.sid === sid && (
        <div className="spp-busy" data-testid="prompt-busy" role="status">
          <span className="spp-busy-line">{busy.line}</span>
          <Button size="sm" variant="primary" onClick={() => void resolveBusy("queue")} disabled={sending} data-testid="prompt-queue" title="Hold it: it starts the moment the running turn ends">Queue it</Button>
          <Button size="sm" onClick={() => void resolveBusy("steer")} disabled={sending} data-testid="prompt-steer" title="Send it into the running turn now">Steer</Button>
          <Button size="sm" variant="ghost" onClick={() => void resolveBusy("cancel")} data-testid="prompt-busy-cancel" title="Keep the text in the box">Cancel</Button>
        </div>
      )}
      {matches.length > 0 && !modelPick && (
        <ul className="spp-slash" data-testid="prompt-slash-list" role="listbox" aria-label="Slash commands">
          {matches.map((r, i) => (
            <li key={r.name} role="option" aria-selected={i === at} className="spp-slash-item" data-testid="prompt-slash-item" data-name={r.name} data-on={i === at || undefined}
                onMouseDown={(e) => (e.preventDefault(), setDraft(`/${r.name} `), box.current?.focus())}>
              <span className="mono spp-slash-name">/{r.name}</span>
              {r.args && <span className="mono muted spp-slash-args">{r.args}</span>}
              <span className="spp-slash-help">{r.help}</span>
            </li>
          ))}
        </ul>
      )}
      {modelPick && (
        <div className="spp-model" data-testid="prompt-model-picker">
          <ModelPicker value="" tid="prompt-model" autoFocus bare onPick={(ref) => (setDraft(ref ? `/model ${ref}` : draft), backToBox())}
                       onClose={() => (setClosed(draft), backToBox())} />
        </div>
      )}
      <div className="spp-row-in">
        <span className="spp-caret mono" aria-hidden="true">›</span>
        <TextBox ref={box} fill mono className="spp-input" value={draft} disabled={!!off} readOnly={ended} placeholder={off || "Type a turn, or / for a command"}
                 onChange={(e) => (edited(e.target.value), setPick(0))} onKeyDown={onKey} aria-label="Type into this session" data-testid="prompt-input" />
        <Button size="sm" variant="primary" icon={<Icon name="send" />} disabled={!!off || ended || sending || (!draft.trim() && !img)} onClick={go} data-testid="prompt-send">
          Send
        </Button>
      </div>
      {(img || imgError) && (
        <div className="spp-chip mono" data-testid="prompt-image" data-error={imgError ? true : undefined}>
          {img ? `${img.name} · ${img.width && img.height ? `${img.width}×${img.height} · ` : ""}${kb(img.bytes)}` : imgError}
          <button type="button" className="og-link" data-testid="prompt-image-clear" onClick={() => prompt.update(() => ({ img: null, imgError: "" }))}>remove</button>
        </div>
      )}
    </div>
  );
}
