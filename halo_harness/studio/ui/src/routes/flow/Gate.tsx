// The human gate, answered from Studio: the open gate's text (the render's
// prompt, or an org position's draft), then Confirm / Redo with an
// instruction / Stop, posted to `flow/runs/<id>/answer` (the same answer file
// `halo flow answer` writes). After an answer the band says what was decided.
import { useState } from "react";
import { Button } from "../../lib/ui";
import { answerGate } from "./actions";
import { useFlow } from "./store";
import type { Gate } from "./types";

/** The gate's text without the artboard file paths (they show as images). */
export function gateText(g: Gate): string {
  return String(g.text || "")
    .split("\n")
    .filter((l) => !/^([A-Za-z]:[\\/]|\/)\S+\.(png|jpe?g|webp|gif|mp4|webm|mov)$/i.test(l.trim()))
    .join("\n")
    .trim();
}

/** What was decided at `step` in the open run from here (the last answer), else "". */
export function useAnswered(step: string | undefined): string {
  return useFlow((s) => {
    if (!step || !s.runId) return "";
    const keys = Object.keys(s.answered).filter((k) => k.startsWith(`${s.runId}:${step}:`));
    return keys.length ? s.answered[keys[keys.length - 1]] : "";
  });
}

const PAST: Record<string, string> = { accept: "accepted", redo: "sent back to redo", stop: "stopped" };

export function AnsweredBand({ action, detail }: { action: string; detail?: string }) {
  if (!action) return null;
  return (
    <div className="fl-band mono" data-action={action} data-motion={action === "accept" ? "done" : action === "stop" ? "error" : "working"} data-testid="gate-answered">
      {(PAST[action] || action).toUpperCase()}
      {detail && <span className="muted"> · {detail}</span>}
    </div>
  );
}

export function GateCard({ gate, compact }: { gate: Gate; compact?: boolean }) {
  const [instruction, setInstruction] = useState("");
  const [busy, setBusy] = useState(false);
  const confirm = !gate.position || gate.position === "You";
  const go = async (action: "accept" | "redo" | "stop") => {
    setBusy(true);
    const ok = await answerGate(action, action === "redo" ? instruction : "");
    setBusy(false);
    if (ok) setInstruction("");
  };
  const text = gateText(gate);
  return (
    <div className="fl-gatecard" data-motion="waiting" data-testid="gate-card">
      <div className="fl-gatecard-head">
        <span className="glance-kicker mono fl-warn">WAITING ON YOU</span>
        <span className="mono muted">
          {gate.step}
          {gate.position && gate.position !== "You" ? ` · ${gate.position}` : ""} · round {gate.round}
        </span>
      </div>
      {text && !compact && <p className="fl-gate-text">{text}</p>}
      <div className="fl-gate-actions">
        <Button variant="primary" size="sm" disabled={busy} onClick={() => void go("accept")} title={confirm ? "Keep this render and move on" : "Accept the position's work"}>
          {confirm ? "Confirm" : "Accept"}
        </Button>
        <input
          className="input fl-instruction"
          placeholder={confirm ? "what to change (warmer colours, a wider shot...)" : "what the position should change"}
          value={instruction}
          onChange={(e) => setInstruction(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && instruction.trim() && void go("redo")}
          aria-label="Redo instruction"
        />
        <Button size="sm" disabled={busy || !instruction.trim()} onClick={() => void go("redo")} title={confirm ? "Render again with the instruction added to the prompt" : "Run the position again with the instruction"}>
          Redo
        </Button>
        <Button variant="danger" size="sm" disabled={busy} onClick={() => void go("stop")} title="Stop the run here">
          Stop
        </Button>
      </div>
    </div>
  );
}
