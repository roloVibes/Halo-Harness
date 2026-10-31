// The Steer box: talk to this one agent. A nudge is a note it reads before
// its next model call; a redirect replaces its task. It posts `steer` to the
// agent's command route and the stream echoes it at once, marked "you".
// Enter sends, Shift+Enter is a new line, Esc leaves the box.
// 3.1.7.0 R1: Session's Live column keeps one at its foot at all times, so a
// box says who it talks to (`head`: "STEER main") and carries what sits beside
// it (`extra`: Pause and Stop). `focusSteer(where)` moves the keyboard into
// the box of `where` ("agent": the Agent panel's, "live": the Live column's);
// each request is taken once, so a box that mounts later does not take it again,
// and lands after the panel that opened with it has taken its own focus.
import { useEffect, useRef, useState, type ReactNode } from "react";
import { Button, Icon } from "../../lib/ui";
import { steer } from "./actions";
import { fleet, useFleet } from "./store";

export type SteerWhere = "agent" | "live";
let want: SteerWhere = "agent";
let taken = 0;

/** Put the keyboard in the Steer box of `where` (the store's `steerFocus` is the request count). */
export function focusSteer(where: SteerWhere = "agent"): void {
  want = where;
  fleet.update((s) => ({ steerFocus: s.steerFocus + 1 }));
}

// 3.3.6.0 R6: `send` takes the steer instead (Session's Live box with an image attached: session/steerImage.ts);
// it answers null when it has nothing to add and the plain steer goes as before
type Props = { k: string; disabled: boolean; why?: string; where?: SteerWhere; head?: ReactNode; extra?: ReactNode;
  send?: (text: string, mode: "nudge" | "redirect") => Promise<boolean> | null };

export function Steer({ k, disabled, why, where = "agent", head, extra, send: sendVia }: Props) {
  const [text, setText] = useState("");
  const [mode, setMode] = useState<"nudge" | "redirect">("nudge");
  const [busy, setBusy] = useState(false);
  const focus = useFleet((s) => s.steerFocus);
  const box = useRef<HTMLTextAreaElement>(null);
  useEffect(() => {
    if (focus <= taken || want !== where) return;
    taken = focus;
    // after this commit's other effects: a panel brought up with it (openAgentPanel's focusPanel) takes the focus
    // first, and on a slow host it can take it back after our first tick too -- so keep asking, a few ticks apart,
    // until the box holds the keyboard or 1.2 s has passed (3.1.7.0: the Linux runner lost it every time)
    const delays = [0, 50, 150, 300, 600, 1200];
    const timers = delays.map((ms) => window.setTimeout(() => {
      const el = box.current;
      if (el && document.activeElement !== el) el.focus({ preventScroll: true });
    }, ms));
    return () => timers.forEach((t) => window.clearTimeout(t));
  }, [focus, where]);
  const send = async () => {
    if (!text.trim() || busy) return;
    setBusy(true);
    const ok = await (sendVia?.(text, mode) ?? steer(k, text, mode));
    setBusy(false);
    if (ok) setText("");
  };
  return (
    <div className="fa-steer" data-disabled={disabled || undefined}>
      <div className="fa-steer-head">
        {head || <span className="rail-label mono">STEER THIS AGENT</span>}
        <div className="segmented fa-mode" role="group" aria-label="How to steer">
          {(["nudge", "redirect"] as const).map((m) => (
            <button key={m} className={mode === m ? "on" : ""} aria-pressed={mode === m} onClick={() => setMode(m)} title={m === "nudge" ? "A note it reads before its next step" : "Replace its task with this one"}>
              {m}
            </button>
          ))}
        </div>
        {extra && <div className="fa-steer-extra">{extra}</div>}
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
