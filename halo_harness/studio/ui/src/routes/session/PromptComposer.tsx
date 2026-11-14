// The Prompt panel's box (3.3.11.0 R1): it behaves like the terminal's prompt. Enter sends, Shift+Enter is a new
// line, Up / Down walk this session's history (kept in this browser) when the caret is on the first / last line;
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
import { history, loadSlash, prompt, setDraft, slashMatches, usePrompt } from "./promptStore";
import { ModelPicker } from "../shared/picker/ModelPicker";
import { resolveBusy, send } from "./promptSend";
import { imageFile, kb, readImage } from "./steerImage";

const firstLine = (el: HTMLTextAreaElement) => !el.value.slice(0, el.selectionStart).includes("\n");
const lastLine = (el: HTMLTextAreaElement) => !el.value.slice(el.selectionEnd).includes("\n");

function droppedPath(dt: DataTransfer | null): string {
  const uri = (dt?.getData("text/uri-list") || "").split(/\r?\n/).find((x) => x && !x.startsWith("#")) || "";
  if (uri.startsWith("file://")) return decodeURIComponent(uri.replace(/^file:\/\/(localhost)?/, "").replace(/^\/([A-Za-z]:)/, "$1"));
  return (dt?.getData("text/plain") || uri).trim();
}

export function PromptComposer({ sid, off }: { sid: string; off: string }) {
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
  useEffect(() => void loadSlash(sid), [sid]);
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
    setHist(-1);
    void send(sid, draft);
  };
  const walk = (dir: -1 | 1, e: KeyboardEvent<HTMLTextAreaElement>) => {
    const h = history(sid);
    if (!h.length) return;
    const next = hist < 0 ? (dir < 0 ? h.length - 1 : -1) : hist + dir;
    if (next < -1 || next >= h.length) return;
    e.preventDefault();
    setHist(next);
    setDraft(next < 0 ? "" : h[next]);
  };
  const onKey = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    const el = e.currentTarget;
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
      if (matches.length && matches[at] && matches[at].name !== typed) complete();
      else go();
    } else if (e.key === "ArrowUp" && !e.shiftKey && firstLine(el)) walk(-1, e);
    else if (e.key === "ArrowDown" && !e.shiftKey && lastLine(el) && hist >= 0) walk(1, e);
  };
  const take = async (e: ClipboardEvent<HTMLDivElement> | DragEvent<HTMLDivElement>, from: "paste" | "drop") => {
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
      setDraft(draft + (draft && !/\s$/.test(draft) ? " " : "") + path);
    }
  };
  return (
    <div className="spp-composer" data-testid="prompt-composer" data-disabled={!!off || undefined} onPaste={(e) => void take(e, "paste")}
         onDrop={(e) => void take(e, "drop")} onDragOver={(e) => e.dataTransfer?.types?.length && e.preventDefault()}>
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
        <TextBox ref={box} fill mono className="spp-input" value={draft} disabled={!!off} placeholder={off || "Type a turn, or / for a command"}
                 onChange={(e) => (setDraft(e.target.value), setPick(0))} onKeyDown={onKey} aria-label="Type into this session" data-testid="prompt-input" />
        <Button size="sm" variant="primary" icon={<Icon name="send" />} disabled={!!off || sending || (!draft.trim() && !img)} onClick={go} data-testid="prompt-send">
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
