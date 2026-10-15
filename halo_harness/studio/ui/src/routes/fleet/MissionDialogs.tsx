// The Mission panel's two dialogs (3.0.6.0 R8), mounted beside the other
// Fleet dialogs (App.tsx): Stop the mission (asks first, with a reason the
// report keeps; every running part is asked to stop, done parts stay done)
// and the text viewer for a file of the mission folder (an artifact, a
// part's hand-back), read with `GET .../files?path=`.
import { useState } from "react";
import { Button, Dialog } from "../../lib/ui";
import { closeFile, stopIt } from "./mload";
import { missions, useMissions } from "./mstore";

function StopAsk() {
  const [reason, setReason] = useState("");
  const goal = useMissions((s) => s.view?.mission.goal || "");
  const close = () => missions.update(() => ({ stopAsk: false }));
  return (
    <Dialog open onClose={close} title="Stop the mission?" kicker="FLEET · MISSION" testid="fleet-mission-stop-ask"
            footer={<><Button onClick={close}>Keep it running</Button><Button variant="danger" onClick={() => void stopIt(reason.trim())} data-testid="fleet-mission-stop-yes">Stop it</Button></>}>
      <p>{goal}</p>
      <p className="muted">Every running part is asked to stop on its harness, parts still waiting are skipped, and the mission ends stopped. What is done stays done; the report keeps your reason.</p>
      <input className="input" value={reason} onChange={(e) => setReason(e.target.value)} placeholder="why (optional, goes into the report)" data-testid="fleet-mission-stop-reason"
             onKeyDown={(e) => e.key === "Enter" && void stopIt(reason.trim())} />
    </Dialog>
  );
}

function Viewer() {
  const f = useMissions((s) => s.file);
  if (!f) return null;
  return (
    <Dialog open onClose={closeFile} title={f.path} kicker={`FLEET · MISSION FILE · ${Math.max(1, Math.round(f.size / 1024))} KB`} testid="fleet-mission-file"
            footer={<Button onClick={closeFile}>Close</Button>}>
      <pre className="fmi-file-text mono" data-testid="fleet-mission-file-text">{f.text}</pre>
      {f.truncated && <p className="muted">Only the first 2 MB are shown.</p>}
    </Dialog>
  );
}

export function MissionDialogs() {
  const ask = useMissions((s) => s.stopAsk);
  return (
    <>
      {ask && <StopAsk />}
      <Viewer />
    </>
  );
}
