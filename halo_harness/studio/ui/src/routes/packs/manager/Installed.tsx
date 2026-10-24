// pm-installed (3.2.0.0 R6): every pack here, one row each -- its id, name and
// version, enabled or not, the grants given of the ones it requests, its
// health (the doctor's rows for it) and what keeps it from running here (the
// doctor's words) -- with Enable (the grants picked in Details), Disable,
// Update and Remove. Remove asks first, naming what goes, what stays and the
// command it runs. A click on a row selects the pack for Details, Settings
// and Templates. Under the rows: the last action's lines, as `halo pack` printed them.
import { useState } from "react";
import { Button, Dialog, Empty } from "../../../lib/ui";
import { cli, disablePack, enablePack, mgr, removePack, selectPack, updatePack, useMgr } from "./store";
import type { PackRow } from "./types";

const NONE: string[] = [];

function stateWord(p: PackRow): string {
  return p.running ? "enabled" : p.state;
}

function Row({ p, on }: { p: PackRow; on: boolean }) {
  const busy = useMgr((s) => !!s.busy);
  const picks = useMgr((s) => s.picks[p.id] || NONE); // a stable empty list: a new [] per read re-renders forever
  const warn = p.compat[0] || "";
  const health = p.health.length;
  return (
    <li className="pm-row" data-on={on || undefined} data-state={p.running ? "running" : p.enabled ? "enabled" : "disabled"}
        data-testid="pm-installed-row" data-id={p.id}>
      <button className="pm-row-main" aria-pressed={on} onClick={() => selectPack(p.id)} title={p.description}>
        <span className="pm-row-id mono">{p.id}</span>
        <span className="pm-row-name">{p.name}</span>
        <span className="pm-row-ver mono muted">{p.version}</span>
        <span className="og-chip mono pm-state" data-testid="pm-state">{stateWord(p)}</span>
        <span className="og-chip mono" title={p.requested.length ? `requests: ${p.requested.join(", ")}` : "it requests no permissions"} data-testid="pm-grants">
          {p.granted.length}/{p.requested.length} granted
        </span>
        {health > 0 && (
          <span className="og-chip mono pm-warn" title={p.health.map((h) => h.text).join("\n")} data-testid="pm-health-count">
            {health} doctor line{health === 1 ? "" : "s"}
          </span>
        )}
        {warn && <span className="pm-row-warn" data-testid="pm-row-warn">{warn}</span>}
      </button>
      <span className="pm-row-acts">
        {!p.enabled && (
          <Button size="sm" variant="primary" disabled={busy} onClick={() => void enablePack(p.id, picks)} title={cli.enable(p.id, picks)} data-testid="pm-enable">
            Enable{picks.length ? ` (${picks.length} grant${picks.length === 1 ? "" : "s"})` : ""}
          </Button>
        )}
        {p.enabled && (
          <Button size="sm" disabled={busy} onClick={() => void disablePack(p.id)} title={`${cli.disable(p.id)}: nothing of it runs; its grants are cleared`} data-testid="pm-disable">
            Disable
          </Button>
        )}
        <Button size="sm" variant="ghost" disabled={busy || !p.installed} onClick={() => void updatePack(p.id)} title={cli.update(p.id)} data-testid="pm-update">
          Update
        </Button>
        <Button size="sm" variant="ghost" disabled={busy} onClick={() => mgr.update(() => ({ removing: p.id }))} title={`${cli.remove(p.id, false)} (asks first)`} data-testid="pm-remove">
          Remove
        </Button>
      </span>
    </li>
  );
}

function RemoveDialog() {
  const id = useMgr((s) => s.removing);
  const [keep, setKeep] = useState(false);
  const close = () => (mgr.update(() => ({ removing: "" })), setKeep(false));
  if (!id) return null;
  const yes = async () => {
    close();
    await removePack(id, keep);
  };
  return (
    <Dialog open onClose={close} title={`Remove ${id}?`} kicker="PACKS · REMOVE" testid="pm-remove-dialog"
            footer={<><Button onClick={close}>Cancel</Button><Button variant="danger" onClick={() => void yes()} data-testid="pm-remove-yes">Remove</Button></>}>
      <p>Removes the pack's own files: the ones its install or update wrote that still hold what it wrote. A file of its folder you changed stays, and so does everything of yours: your bios and lineups, your settings, the memory folders. Each one is listed after.</p>
      <label className="og-switch mono">
        <input type="checkbox" checked={keep} onChange={(e) => setKeep(e.target.checked)} data-testid="pm-keep-config" />
        Keep its record and grants for a later install
      </label>
      <code className="pk-grant-cmd" data-testid="pm-remove-cmd">{cli.remove(id, keep)}</code>
    </Dialog>
  );
}

function Last() {
  const last = useMgr((s) => s.last);
  if (!last) return null;
  return (
    <div className="pm-last" data-ok={last.ok || undefined} data-testid="pm-last">
      <div className="rail-label mono">{last.what.toUpperCase()}</div>
      <pre className="pm-lines mono">{last.lines.join("\n")}</pre>
    </div>
  );
}

export function InstalledDetail() {
  const data = useMgr((s) => s.data);
  const error = useMgr((s) => s.error);
  const sel = useMgr((s) => s.sel);
  if (!data) return error ? <Empty title="Studio could not read the packs" body={error} testid="pm-error" /> : <div className="og-wait mono muted">reading the packs...</div>;
  return (
    <div className="pm-installed" data-testid="pm-installed-body">
      {data.packs.length ? (
        <ul className="pm-rows">
          {data.packs.map((p) => (
            <Row key={p.id} p={p} on={p.id === sel} />
          ))}
        </ul>
      ) : (
        <Empty title="No pack is installed here" body="Sources lists the packs you can install: the folders and git urls of packs.sources, and the Documentation Review pack Halo ships." testid="pm-installed-empty" />
      )}
      {data.problems.map((h) => (
        <p key={h.text} className="pm-row-warn">{h.text}{h.fix ? ` -> ${h.fix}` : ""}</p>
      ))}
      <Last />
      <RemoveDialog />
    </div>
  );
}

export function InstalledGlance() {
  const n = useMgr((s) => s.data?.packs.length ?? 0);
  const on = useMgr((s) => s.data?.packs.filter((p) => p.running).length ?? 0);
  return (
    <div className="glance">
      <div className="glance-kicker mono">INSTALLED</div>
      <div className="glance-text mono">{n} pack{n === 1 ? "" : "s"}</div>
      <div className="glance-hint">{on} running</div>
    </div>
  );
}
