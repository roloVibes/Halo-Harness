// Inviting another harness and what this one shares: the pair card (a
// one-time six-word code, the `halo fleet join` line to type on the other
// machine and its QR, drawn from POST fleet/pair's matrix; Start the hub when
// none runs here), the share / control settings as plain radio rows
// (fleet.share, fleet.allow_control), and the hubs this harness joined and
// the members of this machine's hub (Kick).
import { useEffect, useState } from "react";
import { Button, Icon } from "../../lib/ui";
import { toast } from "../../lib/store";
import { kick, loadSettings, pairCode, saveSetting, startHub, type PairCode, type Settings } from "./actions";

export function QR({ matrix }: { matrix: number[][] }) {
  const n = matrix.length;
  let d = "";
  matrix.forEach((row, y) => row.forEach((on, x) => on && (d += `M${x + 4} ${y + 4}h1v1h-1z`)));
  return (
    <svg className="fp-qr" viewBox={`0 0 ${n + 8} ${n + 8}`} role="img" aria-label="QR code for the join address" data-testid="fleet-qr" shapeRendering="crispEdges">
      <rect width={n + 8} height={n + 8} className="fp-qr-bg" />
      <path d={d} className="fp-qr-dots" />
    </svg>
  );
}

export function PairCard() {
  const [code, setCode] = useState<PairCode | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const make = async () => {
    setBusy(true);
    const r = await pairCode();
    setBusy(false);
    if (typeof r === "string") setError(r);
    else {
      setCode(r);
      setError("");
    }
  };
  const copy = () => {
    if (!code) return;
    void navigator.clipboard?.writeText(code.join).then(() => toast("The join line is on the clipboard", "done"), () => toast("Copy it by hand: the clipboard is off here", "info"));
  };
  return (
    <section className="fp-pair" data-testid="fleet-pair">
      <div className="rail-label mono">INVITE ANOTHER HARNESS</div>
      {!code ? (
        <div className="fp-start">
          <p className="muted">A one-time code admits one harness to this machine's hub; on the other machine you type it into <code>halo fleet join</code>.</p>
          <Button variant="primary" icon={<Icon name="link" />} onClick={() => void make()} disabled={busy} data-testid="fleet-pair-make">
            Make a pair code
          </Button>
        </div>
      ) : (
        <div className="fp-code-grid">
          <QR matrix={code.matrix} />
          <div className="fp-code-side">
            <div className="fp-code mono" data-testid="fleet-pair-code">{code.code}</div>
            <div className="muted">On the other machine:</div>
            <code className="fp-join mono">{code.join}</code>
            <div className="og-actions">
              <Button size="sm" onClick={copy}>Copy the line</Button>
              <Button size="sm" variant="ghost" onClick={() => void make()}>New code</Button>
            </div>
            <div className="mono muted fp-note">
              one harness, {Math.max(1, Math.round(code.ttl / 60))} min · hub {code.url}
              {code.fingerprint ? ` · TLS ${code.fingerprint.slice(0, 16)}` : ""}
            </div>
            {!code.hub_running && (
              <div className="fp-nohub">
                <span>No hub runs here yet: the code waits for one.</span>
                <Button size="sm" onClick={() => void startHub().then((ok) => { if (ok) void make(); })}>Start the hub here</Button>
                <span className="muted">It listens on the LAN port; Windows asks once about its firewall.</span>
              </div>
            )}
          </div>
        </div>
      )}
      {error && <p className="og-problems">{error}</p>}
    </section>
  );
}

const SHARE: [string, string][] = [
  ["status", "sessions and agent trees: who runs what, states and cost"],
  ["events", "and every event: tool calls, cards, results (no text as it is typed)"],
  ["full", "and what each agent types, as it types it"],
];
const CONTROL: [string, string][] = [
  ["none", "watch only: the hub sends no command here"],
  ["ask", "each command opens a card in your terminal: allow or deny"],
  ["all", "commands run as if you typed them here"],
];

function Radios({ name, value, rows, onPick }: { name: string; value: string; rows: [string, string][]; onPick: (v: string) => void }) {
  return (
    <div className="fp-radios" role="radiogroup" aria-label={name}>
      {rows.map(([v, text]) => (
        <label key={v} className="fp-radio" data-on={value === v || undefined}>
          <input type="radio" name={name} value={v} checked={value === v} onChange={() => onPick(v)} />
          <b className="mono">{v}</b>
          <span className="muted">{text}</span>
        </label>
      ))}
    </div>
  );
}

export function FleetSettings() {
  const [s, setS] = useState<Settings | null>(null);
  const [error, setError] = useState("");
  useEffect(() => {
    loadSettings().then(setS, (e) => setError(String(e?.message || e)));
  }, []);
  if (error) return <p className="og-problems">{error}</p>;
  if (!s) return <div className="og-wait mono muted">reading the fleet settings...</div>;
  const pick = (k: "share" | "allow_control") => async (v: string) => {
    const next = await saveSetting(k, v);
    if (next) setS(next);
  };
  return (
    <section className="fp-settings" data-testid="fleet-settings">
      <div className="rail-label mono">WHEN {s.name.toUpperCase()} JOINS A HUB, IT SHARES</div>
      <Radios name="share" value={s.share} rows={SHARE} onPick={pick("share")} />
      <div className="rail-label mono">WHAT A HUB MAY DO HERE</div>
      <Radios name="allow_control" value={s.allow_control} rows={CONTROL} onPick={pick("allow_control")} />
      <div className="rail-label mono">HUBS THIS HARNESS JOINED · {s.hubs.length}</div>
      {s.hubs.length ? (
        <ul className="fp-list">
          {s.hubs.map((h) => (
            <li key={h.url}><b>{h.name || h.url}</b> <span className="mono muted">{h.url} · {h.state || "joined"}</span></li>
          ))}
        </ul>
      ) : (
        <p className="muted fp-none">None yet: <code>halo fleet join &lt;url&gt; --code "..."</code> joins one.</p>
      )}
      <div className="rail-label mono">MEMBERS OF THIS MACHINE'S HUB · {s.members.length}</div>
      {s.members.length ? (
        <ul className="fp-list">
          {s.members.map((m) => (
            <li key={m.id}>
              <b>{m.name || m.id.slice(0, 8)}</b> <span className="mono muted">{[m.host, m.version].filter(Boolean).join(" · ")}</span>
              <button className="og-link mono" onClick={() => void kick(m.id, m.name || m.id).then(() => loadSettings().then(setS))}>kick</button>
            </li>
          ))}
        </ul>
      ) : (
        <p className="muted fp-none">Nobody yet: make a pair code for the first one.</p>
      )}
    </section>
  );
}
