// The Steer box: talk to this one agent. A nudge is a note it reads before
// its next model call; a redirect replaces its task. It posts `steer` to the
// agent's command route and the stream echoes it at once, marked "you".
// Enter sends, Shift+Enter is a new line, Esc leaves the box.
import { useEffect, useRef, useState } from "react";
import { Button, Icon } from "../../lib/ui";
import { steer } from "./actions";
import { useFleet } from "./store";

export function Steer({ k, disabled, why }: { k: string; disabled: boolean; why?: string }) {
  const [text, setText] = useState("");
  const [mode, setMode] = useState<"nudge" | "redirect">("nudge");
  const [busy, setBusy] = useState(false);
  const focus = useFleet((s) => s.steerFocus);
  const box = useRef<HTMLTextAreaElement>(null);
  useEffect(() => {
    if (focus) box.current?.focus({ preventScroll: true });
  }, [focus]);
  const send = async () => {
    if (!text.trim() || busy) return;
    setBusy(true);
    const ok = await steer(k, text, mode);
    setBusy(false);
    if (ok) setText("");
  };
  return (
    <div className="fa-steer" data-disabled={disabled || undefined}>
      <div className="fa-steer-head">
        <span className="rail-label mono">STEER THIS AGENT</span>
        <div className="segmented fa-mode" role="group" aria-label="How to steer">
          {(["nudge", "redirect"] as const).map((m) => (
            <button key={m} className={mode === m ? "on" : ""} aria-pressed={mode === m} onClick={() => setMode(m)} title={m === "nudge" ? "A note it reads before its next step" : "Replace its task with this one"}>
              {m}
            </button>
          ))}
        </div>
      </div>
      <div className="fa-steer-row">
        <textarea
          ref={box}
          className="input fa-steer-text"
          rows={2}
          value={text}
          disabled={disabled}
          placeholder={disabled ? why || "It has finished: nothing to steer" : mode === "nudge" ? "Say what to change; it reads it before its next step" : "The new task it works on instead"}
          onChange={(e) => setText(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey) {
              e.preventDefault();
              void send();
            } else if (e.key === "Escape") box.current?.blur();
          }}
          aria-label="Steer this agent"
          data-testid="fleet-steer"
        />
        <Button size="sm" variant="primary" icon={<Icon name="send" />} disabled={disabled || !text.trim() || busy} onClick={() => void send()} data-testid="fleet-steer-send">
          Send
        </Button>
      </div>
    </div>
  );
}
