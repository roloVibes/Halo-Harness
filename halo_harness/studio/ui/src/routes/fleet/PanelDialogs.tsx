// The R4 Fleet dialogs (one at a time, pstore `dialog`): Take over (type the
// new brief: the agent reads it before its next step, recorded as a
// hand-off in both transcripts), Hand to... (pick a harness; a markdown
// hand-off note is written; then the agent stops) and what that made, Message a member's
// owner, Kick a member (asks first), and a finished recording to download.
import { useEffect, useRef, useState } from "react";
import { Button, Dialog } from "../../lib/ui";
import { toast } from "../../lib/store";
import { download, handoff, kickConfirmed, sendNote } from "./extras";
import { closeDialog, usePanels, type Dialog as D } from "./pstore";
import { useFleet } from "./store";

function useFocus<T extends HTMLElement>() {
  const ref = useRef<T>(null);
  useEffect(() => {
    const id = window.setTimeout(() => ref.current?.focus(), 0);
    return () => window.clearTimeout(id);
  }, []);
  return ref;
}

function TakeOver({ d }: { d: Extract<D, { kind: "take_over" }> }) {
  const [brief, setBrief] = useState("");
  const [busy, setBusy] = useState(false);
  const box = useFocus<HTMLTextAreaElement>();
  const go = async () => {
    if (!brief.trim() || busy) return;
    setBusy(true);
    await handoff(d.key, { mode: "take_over", brief: brief.trim() });
    setBusy(false);
  };
  return (
    <Dialog open onClose={closeDialog} title={`Take over ${d.label}`} kicker="FLEET · HAND-OFF" testid="fleet-takeover"
            footer={<><Button onClick={closeDialog}>Cancel</Button><Button variant="primary" disabled={!brief.trim() || busy} onClick={() => void go()} data-testid="fleet-takeover-go">Take over</Button></>}>
      <p className="muted">Your brief replaces what it was doing: it reads it before its next step. Both transcripts record the hand-off and that you made it.</p>
      <textarea ref={box} className="input fd-text" rows={5} value={brief} onChange={(e) => setBrief(e.target.value)} placeholder="What it does now, in your words" data-testid="fleet-takeover-brief"
                onKeyDown={(e) => e.key === "Enter" && (e.ctrlKey || e.metaKey) && void go()} />
    </Dialog>
  );
}

function HandTo({ d }: { d: Extract<D, { kind: "hand_to" }> }) {
  const harnesses = useFleet((s) => s.harnesses);
  const own = d.key.split("|")[0];
  const choices = [...harnesses.filter((h) => h.id !== own), ...harnesses.filter((h) => h.id === own)];
  const [to, setTo] = useState(choices[0]?.id || "");
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);
  const go = async () => {
    if (!to || busy) return;
    setBusy(true);
    await handoff(d.key, { mode: "hand_to", to, ...(note.trim() ? { brief: note.trim() } : {}) });
    setBusy(false);
  };
  return (
    <Dialog open onClose={closeDialog} title={`Hand ${d.label} to...`} kicker="FLEET · HAND-OFF" testid="fleet-handto"
            footer={<><Button onClick={closeDialog}>Cancel</Button><Button variant="primary" disabled={!to || busy} onClick={() => void go()} data-testid="fleet-handto-go">Hand it over</Button></>}>
      <p className="muted">The agent's task, its last hand-back and the files it touched go into a hand-off note in the repo. Then this agent stops.</p>
      {choices.length < 2 && <p className="muted">Only this harness is in the fleet: pair another one to hand work across machines.</p>}
      <label className="fd-field">
        <span className="rail-label mono">TO</span>
        <select className="input" value={to} onChange={(e) => setTo(e.target.value)} data-testid="fleet-handto-to">
          {choices.map((h) => <option key={h.id} value={h.id}>{h.name || h.id.slice(0, 8)}{h.local ? " (here)" : h.online ? "" : " (offline)"}</option>)}
        </select>
      </label>
      <label className="fd-field">
        <span className="rail-label mono">A NOTE FOR THEM (OPTIONAL)</span>
        <input className="input" value={note} onChange={(e) => setNote(e.target.value)} placeholder="what to pick up first" data-testid="fleet-handto-note" />
      </label>
    </Dialog>
  );
}

function Handed({ d }: { d: Extract<D, { kind: "handed" }> }) {
  const o = d.out;
  const copy = () => o.path && void navigator.clipboard?.writeText(o.path).then(() => toast("The path is on the clipboard", "done"), () => toast("Copy it by hand: the clipboard is off here", "info"));
  return (
    <Dialog open onClose={closeDialog} title={`${d.label} went to ${o.to || "?"}`} kicker="FLEET · HAND-OFF" testid="fleet-handed"
            footer={<><Button onClick={closeDialog}>Done</Button><Button variant="primary" onClick={copy} data-testid="fleet-handed-open">Open (copy the path)</Button></>}>
      <p>Hand-off note <code className="mono" data-testid="fleet-handed-ref">{o.path}</code></p>
      {o.note && <p className="muted">{o.note}</p>}
      <p className="muted">The agent was asked to stop; the agent that spawned it gets the hand-back.</p>
    </Dialog>
  );
}

function Message({ d }: { d: Extract<D, { kind: "message" }> }) {
  const [text, setText] = useState("");
  const box = useFocus<HTMLTextAreaElement>();
  return (
    <Dialog open onClose={closeDialog} title={`Message ${d.name}`} kicker="FLEET · PEOPLE" testid="fleet-message"
            footer={<><Button onClick={closeDialog}>Cancel</Button><Button variant="primary" disabled={!text.trim()} onClick={() => void sendNote(d.hid, d.sid, text)} data-testid="fleet-message-send">Send</Button></>}>
      <p className="muted">A note its owner reads in that session; the model never sees it.</p>
      <textarea ref={box} className="input fd-text" rows={3} value={text} onChange={(e) => setText(e.target.value)} data-testid="fleet-message-text" />
    </Dialog>
  );
}

function Recording({ d }: { d: Extract<D, { kind: "recording" }> }) {
  return (
    <Dialog open onClose={closeDialog} title={`Recording of ${d.label}`} kicker="FLEET · RECORDING" testid="fleet-recording"
            footer={<><Button onClick={closeDialog}>Close</Button><Button variant="primary" onClick={() => void download(d.url, d.name)} data-testid="fleet-recording-download">Download {d.name}</Button></>}>
      <p>One HTML file ({Math.max(1, Math.round(d.bytes / 1024))} KB): the three streams, a timeline you can scrub, every tool call and the cost curve. It needs no network: open it in any browser, send it to anyone.</p>
      <p className="muted mono">{d.url}</p>
    </Dialog>
  );
}

export function PanelDialogs() {
  const d = usePanels((s) => s.dialog);
  if (!d) return null;
  if (d.kind === "take_over") return <TakeOver d={d} />;
  if (d.kind === "hand_to") return <HandTo d={d} />;
  if (d.kind === "handed") return <Handed d={d} />;
  if (d.kind === "message") return <Message d={d} />;
  if (d.kind === "recording") return <Recording d={d} />;
  return (
    <Dialog open onClose={closeDialog} title={`Kick ${d.name}?`} kicker="FLEET · PEOPLE" testid="fleet-kick"
            footer={<><Button onClick={closeDialog}>Cancel</Button><Button variant="danger" onClick={() => void kickConfirmed(d.hid, d.name)} data-testid="fleet-kick-yes">Kick it</Button></>}>
      <p>{d.name} leaves this hub; to come back it pairs again with a new code.</p>
    </Dialog>
  );
}
