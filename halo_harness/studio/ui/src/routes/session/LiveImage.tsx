// The steer's image chip (3.3.6.0 R6, steerImage.ts): under the Steer box once an image is pasted, dropped or
// captured -- its name, w x h and size, and a remove button; when the session's model cannot see, the offer's
// line and its three choices as buttons (this turn on the visual lane, a model that sees describes it, the text
// alone), each titled with what it does and costs; the one picked rides with the steer. The pending eyes card of
// a turn already running (the session row's `eyes`, agent/eyes_offer.py) is answered by LiveEyes below it.
import { useState } from "react";
import { Button, Icon } from "../../lib/ui";
import { sessionCommand } from "../fleet/actions";
import { useFleet } from "../fleet/store";
import { chosenSession } from "./store";
import { chooseEyes, clearImage, kb, useSteerImage, type EyesChoice } from "./steerImage";

const WORD: Record<string, string> = { lane: "Visual lane", describe: "Describe it", send: "Text only" };

function Choices({ line, choices, picked, onPick, testid }: { line: string; choices: EyesChoice[]; picked: string; onPick: (id: string) => void; testid: string }) {
  return (
    <div className="slv-eyes" data-testid={testid} role="group" aria-label="the model cannot see the image">
      <div className="slv-eyes-line mono" data-testid={`${testid}-line`}>{line}</div>
      <div className="slv-eyes-keys">
        {choices.map((c) => (
          <Button key={c.id} size="sm" variant={picked === c.id ? "primary" : "ghost"} disabled={!!c.disabled} aria-pressed={picked === c.id}
                  onClick={() => onPick(c.id)} data-testid={`${testid}-${c.id}`} title={`${c.label}: ${c.what}`}>
            {WORD[c.id] || c.id}
          </Button>
        ))}
      </div>
    </div>
  );
}

export function LiveImage() {
  const img = useSteerImage((s) => s.img);
  const error = useSteerImage((s) => s.error);
  const offer = useSteerImage((s) => s.offer);
  const eyes = useSteerImage((s) => s.eyes);
  if (!img && !error) return null;
  return (
    <div className="slv-image-wrap">
      {error && <div className="slv-image-error mono" data-testid="session-steer-image-error">{error}</div>}
      {img && (
        <div className="slv-image og-chip mono" data-testid="session-steer-image" data-name={img.name} data-from={img.from}
             data-w={img.width ?? ""} data-h={img.height ?? ""} title={img.path ? `saved at ${img.path}` : "sent with your next steer"}>
          <Icon name="eye" size={12} /> {img.name} · {img.width && img.height ? `${img.width} x ${img.height}` : "size ?"} · {kb(img.bytes)}
          <button type="button" className="icon-btn" aria-label="remove the image" onClick={clearImage} data-testid="session-steer-image-remove">
            <Icon name="close" size={12} />
          </button>
        </div>
      )}
      {img && offer?.offer && <Choices line={offer.line} choices={offer.choices} picked={eyes} onPick={chooseEyes} testid="session-steer-eyes" />}
    </div>
  );
}

/** A running turn's eyes card (the TUI's menu): the three answers, through the session's command route. */
export function LiveEyes() {
  const ss = useFleet(chosenSession);
  const hid = useFleet((s) => s.scope.harness || "local");
  const [sent, setSent] = useState("");
  const e = ss?.eyes;
  if (!ss || !e || !e.id || sent === e.id) return null;
  const answer = async (choice: string) => {
    setSent(e.id);
    const out = await sessionCommand(hid, ss.session_id, "answer", { kind: "approval", request_id: e.id, action: choice });
    if (!out.ok) setSent("");
  };
  return <Choices line={e.line} choices={e.choices} picked="" onPick={(id) => void answer(id)} testid="session-live-eyes" />;
}
