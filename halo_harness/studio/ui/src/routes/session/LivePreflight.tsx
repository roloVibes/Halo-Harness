// The preflight in the Live composer (3.3.5.0 R4, the prompt budget): when the
// chosen session holds a request that will not fit its local model's window
// (agent/preflight.py; the session row's `preflight` {id, line, switch_to}),
// the line sits above the steer box with the three answers the terminal has as
// keys: Compact (the default), the bigger-window model the host has (named;
// disabled when none fits) and Send anyway. Each answers the session's card
// through `fleet/<harness>/<sid>/command {cmd: answer, kind: approval}`.
import { useState } from "react";
import { Button } from "../../lib/ui";
import { sessionCommand } from "../fleet/actions";
import { useFleet } from "../fleet/store";
import { chosenSession } from "./store";

type Choice = "compact" | "switch" | "send";

export function LivePreflight() {
  const ss = useFleet(chosenSession);
  const hid = useFleet((s) => s.scope.harness || "local");
  const [sent, setSent] = useState("");
  const p = ss?.preflight;
  if (!ss || !p || !p.id || sent === p.id) return null;
  const answer = async (choice: Choice) => {
    setSent(p.id);
    const out = await sessionCommand(hid, ss.session_id, "answer", { kind: "approval", request_id: p.id, action: choice });
    if (!out.ok) setSent("");
  };
  return (
    <div className="slv-preflight" data-testid="session-live-preflight" data-id={p.id} role="group" aria-label="the prompt is larger than the window">
      <div className="slv-preflight-line mono" data-testid="preflight-line">{p.line}</div>
      <div className="slv-preflight-keys">
        <Button size="sm" variant="primary" onClick={() => void answer("compact")} data-testid="preflight-compact"
                title="Compact the conversation to fit the window, then send (the default)">
          Compact
        </Button>
        <Button size="sm" disabled={!p.switch_to} onClick={() => void answer("switch")} data-testid="preflight-switch"
                title={p.switch_to ? `Switch the session to ${p.switch_to}, whose window holds this prompt` : "No model on this host has a window that holds this prompt"}>
          {p.switch_to ? `Bigger window: ${p.switch_to}` : "No bigger window here"}
        </Button>
        <Button size="sm" onClick={() => void answer("send")} data-testid="preflight-send"
                title="Send it as it is: Ollama keeps the start and the tail, so the task goes last">
          Send anyway
        </Button>
      </div>
    </div>
  );
}
