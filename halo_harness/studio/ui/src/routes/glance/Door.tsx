// "Open the glance" (3.4.1.0 R4; the palette's View line and Session's "..." menu): one dialog that says where the
// glance is. On this machine: its address and a button that opens it in a new tab. From a phone: when an SSH server
// answers on this machine (GET glance/door, studio/glance_door.py) the steps for a phone's SSH app, the address and a
// code to scan; when none does, plainly that the page is this-machine-only. Nothing opens by itself, nothing is bound.
import { useEffect, useState } from "react";
import { api, token } from "../../lib/api";
import { createStore, useStore } from "../../lib/store";
import { Button, Dialog } from "../../lib/ui";

export type DoorInfo = { here: string; url: string; port: number; ssh: boolean; lan: string; user: string; steps: string[]; line: string; qr: string[] };
const door = createStore<{ open: boolean }>({ open: false });

export function openGlanceDoor(): void {
  door.update(() => ({ open: true }));
}

/** The palette's line (shell/commands.ts) and Session's "..." row say the same. */
export const GLANCE_HINT = "this Studio as one phone-width page: what runs, what waits on you as big buttons, the spend; where to open it";

function Code({ rows }: { rows: string[] }) {
  const n = rows.length;
  const d = rows.map((r, y) => [...r].map((c, x) => (c === "1" ? `M${x + 2} ${y + 2}h1v1h-1z` : "")).join("")).join("");
  return (
    <svg className="gz-qr" data-testid="glance-door-qr" viewBox={`0 0 ${n + 4} ${n + 4}`} role="img" aria-label="the glance's address as a code to scan">
      <rect className="gz-qr-bg" x="0" y="0" width={n + 4} height={n + 4} />
      <path className="gz-qr-ink" d={d} />
    </svg>
  );
}

export function GlanceDoor() {
  const open = useStore(door, (s) => s.open);
  const [info, setInfo] = useState<DoorInfo | null>(null);
  const [error, setError] = useState("");
  useEffect(() => {
    if (!open) return;
    setInfo(null);
    setError("");
    api.get<DoorInfo>("glance/door").then(setInfo, (e) => setError(String(e?.message || e)));
  }, [open]);
  const close = () => door.update(() => ({ open: false }));
  const here = info ? `${info.here}#t=${token()}` : "";
  return (
    <Dialog open={open} onClose={close} title="Open the glance" kicker="ONE PHONE-WIDTH PAGE" testid="glance-door"
            cost={{ does: "opens the glance in a new tab of this browser", costs: "nothing: it reads and answers through this Studio, no model call", writes: "nothing" }}
            footer={<>
              <Button variant="ghost" onClick={close}>Close</Button>
              <Button variant="primary" disabled={!info} onClick={() => (window.open(here, "_blank", "noopener"), close())} data-testid="glance-door-open">Open it here</Button>
            </>}>
      <p className="muted">What runs now, what waits on you with its answers as big buttons, the spend against its cap, the last three events.</p>
      <p className="muted" data-testid="glance-door-owner">A tab Studio opens can look but not answer (3.4.1.2): to answer from this machine, run halo studio --mode glance in a terminal (or paste the glance's address with Studio's #t= key into a new tab yourself).</p>
      {error && <p className="gz-bad">Studio could not say where the glance is: {error}</p>}
      {!info && !error && <p className="mono muted">reading...</p>}
      {info && (
        <div className="gz-door" data-testid="glance-door-body" data-ssh={info.ssh ? "on" : "off"}>
          <div className="gz-door-row"><span className="gz-h mono">THIS MACHINE</span><code className="gz-addr">{info.here}</code></div>
          <div className="gz-door-row"><span className="gz-h mono">A PHONE</span><span data-testid="glance-door-line">{info.line}</span></div>
          {info.ssh && (
            <>
              <ol className="gz-steps">{info.steps.map((s) => <li key={s}>{s}</li>)}</ol>
              {info.qr.length > 0 && <Code rows={info.qr} />}
              <code className="gz-addr" data-testid="glance-door-url">{info.url}</code>
            </>
          )}
        </div>
      )}
    </Dialog>
  );
}
